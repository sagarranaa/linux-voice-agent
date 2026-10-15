import shutil
import subprocess


class LocalSpeaker:
    """Speaks text using the local eSpeak NG program."""

    def __init__(self):
        self.executable = shutil.which("espeak-ng")

        if self.executable is None:
            raise RuntimeError(
                "eSpeak NG is missing. Install it with: "
                "sudo apt install espeak-ng"
            )

    def speak(self, text: str) -> None:
        if not text.strip():
            return

        subprocess.run(
            [self.executable, "-s", "165", "--stdin"],
            input=text,
            text=True,
            check=True,
            timeout=180,
        )