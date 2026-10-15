from pathlib import Path

from groq import APIConnectionError, APIStatusError
from pydantic import ValidationError

from voice_agent.audio.transcriber import GroqTranscriber
from voice_agent.config import get_settings


def main():
    try:
        settings = get_settings()
    except ValidationError:
        print("Configuration error: check your .env.")
        return

    transcriber = GroqTranscriber(settings)

    try:
        print("Transcription model:", settings.groq_stt_model)
        text = transcriber.transcribe(
            Path("data/recordings/mic-test.wav")
        )
        print("\nRecognized text:", text)
    except APIStatusError as error:
        print("HTTP status:", error.status_code)
        print("Error details:", error.body)
    except APIConnectionError:
        print("Could not connect to Groq. Check your internet connection.")
    except (OSError, ValueError) as error:
        print("Transcription error:", error)
    finally:
        transcriber.close()


if __name__ == "__main__":
    main()
