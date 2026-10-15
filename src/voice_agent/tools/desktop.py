import os
from pathlib import Path
import shutil
import subprocess

from voice_agent.config import get_settings


def require_program(name: str) -> str:
    executable = shutil.which(name)

    if executable is None:
        raise ValueError(f"Required program is not installed: {name}")

    return executable


def resolve_user_directory(name: str) -> Path:
    if name not in {"DESKTOP", "DOWNLOAD"}:
        raise ValueError("Supported directories are DESKTOP and DOWNLOAD.")

    result = subprocess.run(
        [require_program("xdg-user-dir"), name],
        capture_output=True,
        text=True,
        check=True,
        timeout=5,
    )

    directory_text = result.stdout.strip()

    if not directory_text:
        raise ValueError(f"No directory configured for {name}.")

    raw_path = Path(directory_text)

    if not raw_path.is_absolute():
        raise ValueError("Configured user directory must be absolute.")

    path = raw_path.resolve()

    # XDG may return HOME when a special directory is disabled.
    # Do not interpret that as permission for the whole home directory.
    if path == Path.home().resolve():
        raise ValueError(
            f"{name} is disabled or points to your home directory."
        )

    if not path.is_dir():
        raise ValueError(f"Configured directory does not exist: {path}")

    return path


def allowed_roots() -> list[Path]:
    roots = [get_settings().agent_workspace.resolve()]

    for name in ("DESKTOP", "DOWNLOAD"):
        try:
            roots.append(resolve_user_directory(name))
        except ValueError:
            continue

    return roots


def validate_desktop_path(path_text: str) -> Path:
    raw_path = Path(path_text)

    if not raw_path.is_absolute():
        raise ValueError(
            "Provide an absolute path returned by a directory tool."
        )

    if ".." in raw_path.parts:
        raise ValueError("Parent-directory traversal is not allowed.")

    path = raw_path.resolve()

    if not any(path.is_relative_to(root) for root in allowed_roots()):
        raise ValueError(
            "Path must be inside Desktop, Downloads, or the agent workspace."
        )

    return path


def get_user_directory(name: str) -> dict:
    path = resolve_user_directory(name)

    return {
        "name": name,
        "path": str(path),
    }


def open_folder(path: str) -> dict:
    directory = validate_desktop_path(path)

    if not directory.is_dir():
        raise ValueError("Folder does not exist.")

    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        raise ValueError("Opening folders requires a graphical desktop session.")

    try:
        result = subprocess.run(
            [require_program("xdg-open"), str(directory)],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except subprocess.TimeoutExpired:
        return {
            "status": "opening_unconfirmed",
            "path": str(directory),
            "message": "The opener timed out; the folder may still open.",
        }

    if result.returncode != 0:
        raise ValueError(
            f"Could not open folder: {result.stderr.strip()[:500]}"
        )

    return {
        "status": "open_request_sent",
        "path": str(directory),
        "message": "Desktop opener accepted the request; window not verified.",
    }


def create_directory(parent_path: str, name: str) -> dict:
    parent = validate_desktop_path(parent_path)

    if not parent.is_dir():
        raise ValueError("Parent directory does not exist.")

    if (
        not name.strip()
        or name in {".", ".."}
        or "/" in name
        or "\\" in name
        or "\x00" in name
    ):
        raise ValueError("Name must be a single nonempty folder name.")

    target = validate_desktop_path(str(parent / name))
    existed = target.exists()

    if existed and not target.is_dir():
        raise ValueError("A file already exists at that location.")

    target.mkdir(exist_ok=True)

    return {
        "status": "already_exists" if existed else "created",
        "path": str(target),
    }


def initialize_git(path: str) -> dict:
    directory = validate_desktop_path(path)

    if not directory.is_dir():
        raise ValueError("Repository directory does not exist.")

    if directory in allowed_roots():
        raise ValueError(
            "Initialize Git in a project subfolder, not a permitted root."
        )

    metadata = directory / ".git"

    # Avoid following metadata that redirects Git outside this folder.
    if metadata.is_symlink() or metadata.is_file():
        raise ValueError("Redirected Git metadata is not supported.")

    existed = metadata.is_dir()

    # Prevent inherited Git variables from redirecting the operation.
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("GIT_")
    }

    result = subprocess.run(
        [require_program("git"), "init"],
        cwd=directory,
        env=environment,
        capture_output=True,
        text=True,
        timeout=get_settings().tool_timeout_seconds,
    )

    if result.returncode != 0:
        raise ValueError(f"Git initialization failed: {result.stderr[:500]}")

    return {
        "status": "reinitialized" if existed else "initialized",
        "path": str(directory),
        "output": result.stdout.strip()[:1000],
    }