from datetime import datetime, timezone

import psutil


def get_system_usage() -> dict:
    """Return a snapshot of this computer's CPU and memory usage."""
    cpu_percent = psutil.cpu_percent(interval=0.5)
    memory = psutil.virtual_memory()

    gib = 1024 ** 3

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "cpu_percent": cpu_percent,
        "cpu_measurement_seconds": 0.5,
        "memory_percent": memory.percent,
        "memory_total_gib": round(memory.total / gib, 2),
        "memory_available_gib": round(memory.available / gib, 2),
    }
