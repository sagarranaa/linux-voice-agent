import json

from groq import Groq
from groq.types.chat import ChatCompletionMessageParam

from voice_agent.config import Settings
from voice_agent.tools.registry import TOOL_DEFINITIONS, execute_tool


class GroqChatClient:
    """Handles chat requests and approved local tool execution."""

    def __init__(self, settings: Settings):
        self.model = settings.groq_chat_model
        self.max_steps = settings.agent_max_steps

        self.client = Groq(
            api_key=settings.groq_api_key.get_secret_value(),
            timeout=30.0,
            max_retries=1,
        )

    def reply(
        self,
        messages: list[ChatCompletionMessageParam],
    ) -> str:
        # Work on a copy so callers' histories are not modified.
        working_messages = list(messages)

        for step in range(self.max_steps):
            # Reserve the last request for the final answer.
            allow_tools = step < self.max_steps - 1

            response = self.client.chat.completions.create(
                model=self.model,
                messages=working_messages,
                tools=TOOL_DEFINITIONS,
                tool_choice="auto" if allow_tools else "none",
                parallel_tool_calls=False,
                temperature=0.3,
                max_completion_tokens=1000,
            )

            if not response.choices:
                raise ValueError("Groq returned no response choices.")

            message = response.choices[0].message

            if message.tool_calls:
                if not allow_tools:
                    raise ValueError(
                        "Model requested tools after the execution limit."
                    )

                if any(call.type != "function" for call in message.tool_calls):
                    raise ValueError("Unsupported tool-call type.")

                # Preserve the model's tool requests in the conversation.
                working_messages.append({
                    "role": "assistant",
                    "content": message.content,
                    "tool_calls": [
                        {
                            "id": call.id,
                            "type": "function",
                            "function": {
                                "name": call.function.name,
                                "arguments": call.function.arguments,
                            },
                        }
                        for call in message.tool_calls
                    ],
                })

                for call in message.tool_calls:
                    result = execute_tool(
                        call.function.name,
                        call.function.arguments,
                    )

                    working_messages.append({
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": json.dumps(result),
                    })

                continue

            content = message.content

            if not content or not content.strip():
                raise ValueError("Groq returned an empty text response.")

            return content.strip()

        raise ValueError("Agent reached its maximum number of steps.")

    def close(self) -> None:
        self.client.close()