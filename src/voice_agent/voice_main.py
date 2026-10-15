from pathlib import Path
import sqlite3
import subprocess
import time

import sounddevice as sd
from groq import (
    APIConnectionError,
    APIStatusError,
    AuthenticationError,
    RateLimitError,
)
from groq.types.chat import ChatCompletionMessageParam
from pydantic import ValidationError

from voice_agent.agent.client import GroqChatClient
from voice_agent.agent.prompts import SYSTEM_PROMPT
from voice_agent.audio.speaker import LocalSpeaker
from voice_agent.audio.speech_detector import SpeechDetector
from voice_agent.audio.transcriber import GroqTranscriber
from voice_agent.config import get_settings
from voice_agent.storage.database import ConversationStore


def main() -> None:
    try:
        settings = get_settings()
    except ValidationError:
        print("Configuration error: check your .env.")
        return

    try:
        speaker = LocalSpeaker()
    except RuntimeError as error:
        print(error)
        return

    store = None
    session_id = None
    chat = None
    transcriber = None

    try:
        # Open storage and create a new conversation session.
        try:
            store = ConversationStore(Path("data/agent.db"))
            session_id = store.start_session(input_mode="voice")
        except (sqlite3.Error, OSError) as error:
            print(f"Could not initialize conversation storage: {error}")
            return

        chat = GroqChatClient(settings)
        transcriber = GroqTranscriber(settings)
        detector = SpeechDetector(device=0)

        history: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]

        recording_path = Path("data/recordings/current.wav")

        print("Linux Voice Agent — automatic voice conversation")
        print(f"Session: {session_id}")
        print("Completed exchanges will be saved to data/agent.db.")
        print("Stay quiet during calibration, then speak when listening.")
        print("Say 'stop listening' to exit, or press Ctrl+C.")

        while True:
            try:
                path = detector.record(
                    recording_path,
                    silence_seconds=1.2,
                    max_recording_seconds=20.0,
                    wait_seconds=30.0,
                )

                if path is None:
                    continue

                print("Transcribing...")
                text = transcriber.transcribe(path)
                print(f"You said: {text}")

                normalized_text = text.lower().strip().rstrip(".!?")

                if normalized_text == "stop listening":
                    print("Stopping voice session.")
                    break

                user_message: ChatCompletionMessageParam = {
                    "role": "user",
                    "content": text,
                }

                print("Thinking...")
                answer = chat.reply([*history, user_message])
                print(f"\nAgent: {answer}")

                # Save the recognized text and completed response.
                try:
                    store.save_exchange(
                        session_id=session_id,
                        user_text=text,
                        assistant_text=answer,
                    )
                except sqlite3.Error as error:
                    print(f"Could not save this exchange: {error}")

                # Preserve context even if storage or playback fails.
                history.extend([
                    user_message,
                    {"role": "assistant", "content": answer},
                ])

                # Keep the system prompt and latest 10 exchanges.
                history = [history[0], *history[1:][-20:]]

                print("Speaking...")
                try:
                    speaker.speak(answer)
                except (subprocess.SubprocessError, OSError) as error:
                    print(f"Speech output failed: {error}")

                # Allow speaker sound to fade before listening.
                time.sleep(0.3)

            except AuthenticationError:
                print("Authentication failed: check your Groq API key.")
                break

            except RateLimitError:
                print("Groq rate limit reached. Waiting 10 seconds.")
                time.sleep(10)

            except APIStatusError as error:
                print(f"Groq API error: HTTP {error.status_code}")
                print("Stopping session so the API issue can be resolved.")
                break

            except APIConnectionError:
                print("Connection failed or timed out. Retrying shortly.")
                time.sleep(3)

            except (OSError, RuntimeError, sd.PortAudioError) as error:
                print(f"Audio or execution error: {error}")
                print("Stopping session so the issue can be resolved.")
                break

            except ValueError as error:
                print(f"Response error: {error}")
                time.sleep(1)

    except (KeyboardInterrupt, EOFError):
        print("\nSession ended.")

    finally:
        # Nested cleanup ensures later resources close even if one fails.
        try:
            if transcriber is not None:
                transcriber.close()
        finally:
            try:
                if chat is not None:
                    chat.close()
            finally:
                if store is not None:
                    try:
                        if session_id is not None:
                            store.end_session(session_id)
                    except sqlite3.Error as error:
                        print(f"Could not mark session as ended: {error}")
                    finally:
                        store.close()


if __name__ == "__main__":
    main()