from pathlib import Path

import sounddevice as sd
import soundfile as sf


def record_audio(
    output_path: Path,
    duration_seconds: float = 5.0,
    device: int | None = None,
) -> Path:
    """Record a short mono clip and save it as a WAV file."""
    if not 0 < duration_seconds <= 30:
        raise ValueError("Recording duration must be between 0 and 30 seconds.")

    device_info = sd.query_devices(device, kind="input")
    sample_rate = int(device_info["default_samplerate"])

    sd.check_input_settings(
        device=device,
        channels=1,
        dtype="float32",
        samplerate=sample_rate,
    )

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Microphone: {device_info['name']}")
    print(f"Sample rate: {sample_rate} Hz")
    print(f"Speak now — recording for {duration_seconds:g} seconds.")

    try:
        audio = sd.rec(
            frames=int(duration_seconds * sample_rate),
            samplerate=sample_rate,
            channels=1,
            dtype="float32",
            device=device,
        )
        status = sd.wait()
    finally:
        sd.stop()

    if status:
        raise RuntimeError(f"Audio capture problem: {status}")

    sf.write(output_path, audio, sample_rate, subtype="PCM_16")
    print(f"Saved: {output_path.resolve()}")

    return output_path
