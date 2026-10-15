import argparse
from pathlib import Path

import numpy as np
import sounddevice as sd
import soundfile as sf

from voice_agent.audio.recorder import record_audio


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", type=int, default=None)
    args = parser.parse_args()

    input("Press Enter when ready, then speak for five seconds...")

    path = record_audio(
        Path("data/recordings/mic-test.wav"),
        duration_seconds=5,
        device=args.device,
    )

    audio, sample_rate = sf.read(path, dtype="float32")
    peak = float(np.max(np.abs(audio)))

    print(f"Peak amplitude: {peak:.6f}")

    if peak == 0:
        print("All samples are zero. Check input device and microphone mute.")
        return

    input("Press Enter to replay...")
    try:
        sd.play(audio, sample_rate)
        sd.wait()
    finally:
        sd.stop()


if __name__ == "__main__":
    main()
