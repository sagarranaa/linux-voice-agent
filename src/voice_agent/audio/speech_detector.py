from collections import deque
from pathlib import Path
import time

import numpy as np
import sounddevice as sd
import soundfile as sf


class SpeechDetector:
    """Record utterances using a session-level audio threshold."""

    def __init__(self, device: int | None = None):
        self.device = device
        self.threshold = None
        self.sample_rate = None

    def record(
        self,
        output_path: Path,
        silence_seconds: float = 1.2,
        max_recording_seconds: float = 20.0,
        wait_seconds: float = 30.0,
    ) -> Path | None:
        info = sd.query_devices(self.device, kind="input")
        sample_rate = int(info["default_samplerate"])
        block_size = int(sample_rate * 0.1)
        block_seconds = block_size / sample_rate

        sd.check_input_settings(
            device=self.device,
            channels=1,
            dtype="float32",
            samplerate=sample_rate,
        )

        with sd.InputStream(
            device=self.device,
            samplerate=sample_rate,
            channels=1,
            dtype="float32",
            blocksize=0,
            latency="high",
        ) as stream:
            overflow_count = 0

            def read_block():
                nonlocal overflow_count

                block, overflowed = stream.read(block_size)

                if overflowed:
                    overflow_count += 1

                    if overflow_count >= 5:
                        raise RuntimeError(
                            "Repeated microphone overflows."
                        )

                    return None

                return block.copy()

            # Discard initial audio while the stream settles.
            for _ in range(3):
                read_block()

            if (
                self.threshold is None
                or self.sample_rate != sample_rate
            ):
                print("Calibrating — stay quiet for two seconds.")
                levels = []
                deadline = time.monotonic() + 6

                while len(levels) < 20:
                    if time.monotonic() >= deadline:
                        raise RuntimeError(
                            "Microphone calibration timed out."
                        )

                    block = read_block()

                    if block is not None:
                        levels.append(
                            float(np.sqrt(np.mean(block ** 2)))
                        )

                noise = float(np.median(levels))

                # Initial heuristic; tune from real microphone measurements.
                if noise > 0.04:
                    raise RuntimeError(
                        f"Calibration level is too high ({noise:.4f}). "
                        "Stay quiet, reduce microphone gain or background "
                        "noise, and restart."
                    )

                self.threshold = max(0.003, noise * 3)
                self.sample_rate = sample_rate
                print(f"Calibration saved: {self.threshold:.4f}")

            print(f"Listening... threshold: {self.threshold:.4f}")

            pre_roll = deque(maxlen=5)
            frames = []
            loud_duration = 0.0
            quiet_duration = 0.0
            started_at = None
            waiting_at = time.monotonic()

            while True:
                block = read_block()
                now = time.monotonic()

                if block is None:
                    pre_roll.clear()
                    loud_duration = 0.0

                    if started_at is not None:
                        print("Audio lost during speech. Please repeat.")
                        return None

                    if now - waiting_at >= wait_seconds:
                        return None

                    continue

                level = float(np.sqrt(np.mean(block ** 2)))

                if started_at is None:
                    pre_roll.append(block)

                    if level >= self.threshold:
                        loud_duration += block_seconds
                    else:
                        loud_duration = 0.0

                    # Require two consecutive 100 ms blocks.
                    if loud_duration >= 0.2:
                        started_at = now
                        frames.extend(pre_roll)
                        print("Speech started...")

                    elif now - waiting_at >= wait_seconds:
                        print("No speech detected.")
                        return None

                    continue

                frames.append(block)

                if level < self.threshold * 0.7:
                    quiet_duration += block_seconds
                else:
                    quiet_duration = 0.0

                if quiet_duration >= silence_seconds:
                    print("Speech ended.")
                    break

                if now - started_at >= max_recording_seconds:
                    print("Maximum recording duration reached.")
                    break

        audio = np.concatenate(frames, axis=0)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        sf.write(
            output_path,
            audio,
            sample_rate,
            subtype="PCM_16",
        )

        return output_path