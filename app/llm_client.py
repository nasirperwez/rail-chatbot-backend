"""OpenAI LLM Client with tool calling support."""
import json
import logging
from typing import Any, Optional, Union
from openai import AsyncOpenAI

from app.config import settings
from app.models import ChatMessage, McpTool, ToolCall, MessageRole

logger = logging.getLogger(__name__)


class LlmResponse:
    """Response from the LLM - either text or tool calls."""
    pass


class TextResponse(LlmResponse):
    """LLM returned a text response."""

    def __init__(self, text: str):
        self.text = text


class ToolCallsResponse(LlmResponse):
    """LLM requested tool calls."""

    def __init__(self, tool_calls: list[ToolCall]):
        self.tool_calls = tool_calls


class LlmError(LlmResponse):
    """LLM returned an error."""

    def __init__(self, message: str, cause: Optional[Exception] = None):
        self.message = message
        self.cause = cause


class LlmClient:
    """OpenAI client with tool calling support."""

    SYSTEM_PROMPT = """You are a helpful Indian Railways assistant powered by IRCTC tools.
You can help users with:
- Checking PNR status
- Finding trains between stations
- Getting train schedules
- Checking seat availability
- Getting fare information
- Train live status
- And more railway-related queries

When users ask about trains, use the available tools to fetch real-time information.
Always be helpful and provide clear, concise responses.
If a tool returns an error, explain it to the user in a friendly way."""

    def __init__(self):
        self._client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    async def chat(
        self,
        messages: list[ChatMessage],
        tools: Optional[list[McpTool]] = None,
    ) -> Union[TextResponse, ToolCallsResponse, LlmError]:
        """
        Send a chat request to OpenAI.

        Args:
            messages: Conversation history
            tools: Available tools (MCP tools converted to OpenAI format)

        Returns:
            TextResponse if LLM returns text,
            ToolCallsResponse if LLM wants to call tools,
            LlmError if something went wrong
        """
        try:
            # Build OpenAI messages
            openai_messages = [
                {"role": "system", "content": self.SYSTEM_PROMPT}
            ]

            for msg in messages:
                openai_msg: dict[str, Any] = {
                    "role": msg.role.value,
                    "content": msg.content,
                }
                if msg.tool_call_id:
                    openai_msg["tool_call_id"] = msg.tool_call_id
                # Include tool_calls for assistant messages
                if msg.tool_calls:
                    openai_msg["tool_calls"] = [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.arguments),
                            },
                        }
                        for tc in msg.tool_calls
                    ]
                openai_messages.append(openai_msg)

            # Build tools in OpenAI format
            openai_tools = None
            if tools:
                openai_tools = [
                    {
                        "type": "function",
                        "function": {
                            "name": tool.name,
                            "description": tool.description or tool.name,
                            "parameters": tool.input_schema or {"type": "object", "properties": {}},
                        },
                    }
                    for tool in tools
                ]

            # Make the API call
            logger.debug(f"Sending {len(openai_messages)} messages to OpenAI")

            response = await self._client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=openai_messages,
                tools=openai_tools,
                tool_choice="auto" if openai_tools else None,
            )

            choice = response.choices[0]
            message = choice.message

            # Check if LLM wants to call tools
            if message.tool_calls:
                tool_calls = []
                for tc in message.tool_calls:
                    # Parse arguments from JSON string
                    try:
                        args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        args = {}

                    tool_calls.append(
                        ToolCall(
                            id=tc.id,
                            name=tc.function.name,
                            arguments=args,
                        )
                    )

                logger.info(f"LLM requested {len(tool_calls)} tool calls")
                return ToolCallsResponse(tool_calls)

            # LLM returned text
            text = message.content or ""
            logger.debug(f"LLM returned text response: {text[:100]}...")
            return TextResponse(text)

        except Exception as e:
            logger.error(f"LLM error: {e}")
            return LlmError(str(e), e)

    def build_tool_result_message(
        self, tool_call_id: str, result: str
    ) -> ChatMessage:
        """Build a message containing the result of a tool call."""
        return ChatMessage(
            role=MessageRole.TOOL,
            content=result,
            tool_call_id=tool_call_id,
        )

    def build_assistant_tool_call_message(
        self, tool_calls: list[ToolCall]
    ) -> ChatMessage:
        """Build an assistant message that requested tool calls."""
        # This is used to add to conversation history
        return ChatMessage(
            role=MessageRole.ASSISTANT,
            content="",  # Content is empty when tool calls are made
        )
