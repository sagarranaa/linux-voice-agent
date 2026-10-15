from pathlib import Path

from groq import APIConnectionError, APIStatusError, AuthenticationError
from groq.types.chat import ChatCompletionMessageParam
from pydantic import ValidationError
import sounddevice as sd

from voice_agent.agent.client import GroqChatClient
from voice_agent.agent.prompts import SYSTEM_PROMPT
from voice_agent.audio.recorder import record_audio
from voice_agent.audio.transcriber import GroqTranscriber
from voice_agent.config import get_settings


def main() -> None:
    try:
        settings = get_settings()
    except ValidationError:
        print("Configuration error: check your .env.")
        return

    chat = GroqChatClient(settings)
    transcriber = GroqTranscriber(settings)

    history: list[ChatCompletionMessageParam] = [
        {"role": "system", "content": SYSTEM_PROMPT}
    ]
    recording_path = Path("data/recordings/current.wav")

    print("Linux Voice Agent — voice input")
    print("Press Enter to record, or type 'exit' to quit.")

    try:
        while True:
            command = input("\nReady: ").strip().lower()

            if command in {"exit", "quit"}:
                break

            if command:
                print("Press Enter without typing to start recording.")
                continue

            try:
                record_audio(
                    recording_path,
                    duration_seconds=5,
                    device=0,
                )

                print("Transcribing...")
                text = transcriber.transcribe(recording_path)
                print(f"You said: {text}")

                user_message: ChatCompletionMessageParam = {
                    "role": "user",
                    "content": text,
                }

                print("Thinking...")
                answer = chat.reply([*history, user_message])
                print(f"\nAgent: {answer}")

                history.extend([
                    user_message,
                    {"role": "assistant", "content": answer},
                ])
                history = [history[0], *history[1:][-20:]]

            except AuthenticationError:
                print("Authentication failed: check your Groq API key.")
                break
            except APIStatusError as error:
                print(f"Groq API error: HTTP {error.status_code}")
            except APIConnectionError:
                print("Connection failed or timed out. Try again.")
            except (OSError, ValueError, RuntimeError, sd.PortAudioError) as error:
                print(f"Voice pipeline error: {error}")

    except (KeyboardInterrupt, EOFError):
        print("\nSession ended.")
    finally:
        transcriber.close()
        chat.close()


if __name__ == "__main__":
    main()