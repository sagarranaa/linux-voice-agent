from pathlib import Path


class WorkspacePolicy:
    """Restrict file-tool paths to a configured workspace."""

    def __init__(self, workspace: Path):
        self.workspace = Path(workspace).resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)

    def resolve_path(self, relative_path: str) -> Path:
        if not isinstance(relative_path, str) or not relative_path.strip():
            raise ValueError("Provide a nonempty relative path.")

        path = Path(relative_path)

        if path.is_absolute():
            raise ValueError("Absolute paths are not allowed.")

        if ".." in path.parts:
            raise ValueError("Parent-directory traversal is not allowed.")

        resolved = (self.workspace / path).resolve()

        if not resolved.is_relative_to(self.workspace):
            raise ValueError("Path must remain inside the workspace.")

        return resolved