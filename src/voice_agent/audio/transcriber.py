from pathlib import Path

from groq import Groq

from voice_agent.config import Settings


class GroqTranscriber:
    """Converts an audio file into text using Groq."""

    def __init__(self, settings: Settings):
        self.model = settings.groq_stt_model
        self.language = settings.groq_stt_language

        self.client = Groq(
            api_key=settings.groq_api_key.get_secret_value(),
            timeout=30.0,
            max_retries=1,
        )

    def transcribe(self, audio_path: Path) -> str:
        audio_path = Path(audio_path)

        if not audio_path.is_file():
            raise FileNotFoundError(f"Recording not found: {audio_path}")

        with audio_path.open("rb") as audio_file:
            response = self.client.audio.transcriptions.create(
                file=audio_file,
                model=self.model,
                language=self.language,
                prompt=(
                    "Software development terminology: "
                    "API, REST API, HTTP, JSON, Node.js, Python, "
                    "Linux, CPU, SQL, PostgreSQL, dependency injection."
                ),
                response_format="json",
                temperature=0.0,
            )

        text = response.text.strip()

        if not text:
            raise ValueError("No text was recognized from the recording.")

        return text

    def close(self) -> None:
        self.client.close()