import subprocess
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from voice_agent.config import get_settings
from voice_agent.security.policy import WorkspacePolicy
from voice_agent.tools.desktop import (
    create_directory,
    get_user_directory,
    initialize_git,
    open_folder,
)
from voice_agent.tools.file_operations import (
    create_file,
    get_task_directory,
    list_directory,
    select_task_directory,
)
from voice_agent.tools.files import create_folder, list_folder
from voice_agent.tools.system_info import get_system_usage


class ToolArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class NoArguments(ToolArguments):
    pass


class CreateFolderArguments(ToolArguments):
    relative_path: str = Field(min_length=1, max_length=240)


class ListFolderArguments(ToolArguments):
    relative_path: str = Field(default=".", min_length=1, max_length=240)


class UserDirectoryArguments(ToolArguments):
    name: Literal["DESKTOP", "DOWNLOAD"]


class PathArguments(ToolArguments):
    path: str = Field(min_length=1, max_length=4096)


class OptionalPathArguments(ToolArguments):
    path: str | None = Field(default=None, min_length=1, max_length=4096)


class CreateDirectoryArguments(ToolArguments):
    parent_path: str = Field(min_length=1, max_length=4096)
    name: str = Field(min_length=1, max_length=200)


class CreateFileArguments(ToolArguments):
    name: str = Field(min_length=1, max_length=200)
    content: str = Field(default="", max_length=100_000)
    directory_path: str | None = Field(
        default=None,
        min_length=1,
        max_length=4096,
    )


TOOL_SPECS = {
    "get_system_usage": (
        NoArguments,
        "Read current CPU and RAM usage.",
    ),
    "create_folder": (
        CreateFolderArguments,
        "Create a folder relative to the agent workspace.",
    ),
    "list_folder": (
        ListFolderArguments,
        "List workspace entries. Use '.' for the workspace root.",
    ),
    "get_user_directory": (
        UserDirectoryArguments,
        "Resolve the actual Desktop or Downloads directory. "
        "Use DESKTOP or DOWNLOAD. Never guess these paths.",
    ),
    "open_folder": (
        PathArguments,
        "Request opening an existing permitted folder. "
        "If accepted, also select it as the logical task directory. "
        "Supply a resolved absolute path.",
    ),
    "create_directory": (
        CreateDirectoryArguments,
        "Create a folder under an existing permitted parent. "
        "Return its absolute path. Does not change the task directory.",
    ),
    "initialize_git": (
        PathArguments,
        "Initialize Git in an existing permitted project folder, "
        "only when requested by the user.",
    ),
    "select_task_directory": (
        PathArguments,
        "Select an existing permitted folder as the task directory "
        "without opening a window. Use when the user asks to work "
        "inside a folder. Does not change the process working directory.",
    ),
    "get_task_directory": (
        NoArguments,
        "Return the selected task directory, or indicate none is selected.",
    ),
    "list_directory": (
        OptionalPathArguments,
        "List up to 100 entries in a permitted directory. "
        "Omit path to use the selected task directory.",
    ),
    "create_file": (
        CreateFileArguments,
        "Create a UTF-8 text file without overwriting existing content. "
        "Supply a single filename. Omit content for an empty file. "
        "Omit directory_path to use the selected task directory.",
    ),
}


TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": argument_model.model_json_schema(),
        },
    }
    for name, (argument_model, description) in TOOL_SPECS.items()
]


def execute_tool(name: str, arguments_json: str) -> dict:
    specification = TOOL_SPECS.get(name)

    if specification is None:
        return {"error": f"Unsupported tool: {name}"}

    argument_model, _ = specification

    try:
        arguments = argument_model.model_validate_json(arguments_json)
    except ValidationError:
        return {"error": "Invalid tool arguments."}

    print(f"Executing tool: {name}")

    try:
        if name == "get_system_usage":
            result = get_system_usage()

        elif name in {"create_folder", "list_folder"}:
            policy = WorkspacePolicy(get_settings().agent_workspace)

            if name == "create_folder":
                result = create_folder(policy, arguments.relative_path)
            else:
                result = list_folder(policy, arguments.relative_path)

        elif name == "get_user_directory":
            result = get_user_directory(arguments.name)

        elif name == "open_folder":
            result = open_folder(arguments.path)

            if result["status"] == "open_request_sent":
                selected = select_task_directory(result["path"])
                result["task_directory"] = selected["path"]

        elif name == "create_directory":
            result = create_directory(
                arguments.parent_path,
                arguments.name,
            )

        elif name == "initialize_git":
            result = initialize_git(arguments.path)

        elif name == "select_task_directory":
            result = select_task_directory(arguments.path)

        elif name == "get_task_directory":
            result = get_task_directory()

        elif name == "list_directory":
            result = list_directory(arguments.path)

        elif name == "create_file":
            result = create_file(
                name=arguments.name,
                content=arguments.content,
                directory_path=arguments.directory_path,
            )

        else:
            return {"error": "Tool has no execution handler."}

        return {"data": result}

    except subprocess.TimeoutExpired:
        return {"error": "Operation timed out; completion is unconfirmed."}

    except (
        OSError,
        ValueError,
        RuntimeError,
        subprocess.SubprocessError,
    ) as error:
        return {"error": str(error)}