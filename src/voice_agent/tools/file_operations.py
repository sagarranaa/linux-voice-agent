from pathlib import Path

from voice_agent.tools.desktop import validate_desktop_path


# Session-level application state for this single-user process.
_active_directory: Path | None = None


def select_task_directory(path: str) -> dict:
    global _active_directory

    directory = validate_desktop_path(path)

    if not directory.is_dir():
        raise ValueError("Selected directory does not exist.")

    _active_directory = directory

    return {
        "status": "selected",
        "path": str(directory),
    }


def get_task_directory() -> dict:
    if _active_directory is None:
        return {
            "path": None,
            "message": "No task directory selected. Ask the user for a location.",
        }

    directory = validate_desktop_path(str(_active_directory))

    if not directory.is_dir():
        raise ValueError("The selected directory no longer exists.")

    return {"path": str(directory)}


def resolve_directory(path: str | None) -> Path:
    if path is None:
        selected = get_task_directory()

        if selected["path"] is None:
            raise ValueError(
                "No task directory selected. Ask where to perform this action."
            )

        path = selected["path"]

    directory = validate_desktop_path(path)

    if not directory.is_dir():
        raise ValueError("Directory does not exist.")

    return directory


def list_directory(path: str | None = None) -> dict:
    directory = resolve_directory(path)
    entries = []
    truncated = False

    for child in directory.iterdir():
        if len(entries) >= 100:
            truncated = True
            break

        if child.is_symlink():
            kind = "symlink"
        elif child.is_dir():
            kind = "folder"
        else:
            kind = "file"

        entries.append({"name": child.name, "type": kind})

    entries.sort(key=lambda item: item["name"])

    return {
        "path": str(directory),
        "entries": entries,
        "truncated": truncated,
    }


def create_file(
    name: str,
    content: str = "",
    directory_path: str | None = None,
) -> dict:
    directory = resolve_directory(directory_path)

    if (
        not name.strip()
        or name in {".", ".."}
        or "/" in name
        or "\\" in name
        or "\x00" in name
    ):
        raise ValueError("Provide a single nonempty filename.")

    target = validate_desktop_path(str(directory / name))

    try:
        # Exclusive creation: never overwrite an existing file.
        with target.open("x", encoding="utf-8") as file:
            file.write(content)
    except FileExistsError:
        return {
            "status": "already_exists",
            "path": str(target),
            "message": "Existing content was preserved.",
        }

    return {
        "status": "created",
        "path": str(target),
        "bytes_written": len(content.encode("utf-8")),
    }