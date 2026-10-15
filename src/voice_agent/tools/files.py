from voice_agent.security.policy import WorkspacePolicy


def create_folder(
    policy: WorkspacePolicy,
    relative_path: str,
) -> dict:
    path = policy.resolve_path(relative_path)

    if path.exists():
        if not path.is_dir():
            raise ValueError("A file already exists at that path.")

        return {
            "status": "already_exists",
            "path": str(path.relative_to(policy.workspace)),
        }

    path.mkdir(parents=True, exist_ok=True)

    return {
        "status": "created",
        "path": str(path.relative_to(policy.workspace)),
    }


def list_folder(
    policy: WorkspacePolicy,
    relative_path: str = ".",
) -> dict:
    path = policy.resolve_path(relative_path)

    if not path.is_dir():
        raise ValueError("Folder does not exist.")

    entries = []
    truncated = False

    for child in path.iterdir():
        if len(entries) >= 100:
            truncated = True
            break

        if child.is_symlink():
            kind = "symlink"
        elif child.is_dir():
            kind = "folder"
        else:
            kind = "file"

        entries.append({
            "name": child.name,
            "type": kind,
        })

    entries.sort(key=lambda entry: entry["name"])

    return {
        "path": str(path.relative_to(policy.workspace)),
        "entries": entries,
        "truncated": truncated,
    }