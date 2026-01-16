"""Chat Orchestrator - Core AI + MCP tool calling loop."""
import logging
from typing import AsyncGenerator

from app.mcp_client import McpClient
from app.llm_client import (
    LlmClient,
    TextResponse,
    ToolCallsResponse,
    LlmError,
)
from app.models import (
    ChatMessage,
    MessageRole,
    OrchestratorEvent,
    EventType,
    ToolCall,
)

logger = logging.getLogger(__name__)

MAX_TOOL_ITERATIONS = 10


class ChatOrchestrator:
    """
    Orchestrates the chat flow between user, LLM, and MCP tools.

    Flow:
    1. User sends message
    2. Get available tools from MCP
    3. Send message + tools to LLM
    4. If LLM requests tool calls -> execute via MCP -> return to LLM
    5. Repeat until LLM returns final text response
    """

    def __init__(self):
        self.mcp_client = McpClient()
        self.llm_client = LlmClient()

    async def process_message(
        self,
        user_message: str,
        history: list[ChatMessage],
    ) -> AsyncGenerator[OrchestratorEvent, None]:
        """
        Process a user message and yield events as they occur.

        Args:
            user_message: The user's message
            history: Previous conversation history

        Yields:
            OrchestratorEvent for each step (thinking, tool calls, response)
        """
        try:
            # Emit thinking event
            yield OrchestratorEvent(
                type=EventType.THINKING,
                text="Analyzing your request...",
            )

            # Initialize MCP and get tools
            await self.mcp_client.initialize()
            tools = await self.mcp_client.list_tools()

            logger.info(f"Initialized with {len(tools)} tools")

            # Build conversation with user message
            messages = list(history)
            messages.append(
                ChatMessage(role=MessageRole.USER, content=user_message)
            )

            # Tool calling loop
            iterations = 0
            while iterations < MAX_TOOL_ITERATIONS:
                iterations += 1
                logger.debug(f"Tool calling iteration {iterations}")

                # Send to LLM
                llm_response = await self.llm_client.chat(messages, tools)

                if isinstance(llm_response, LlmError):
                    yield OrchestratorEvent(
                        type=EventType.ERROR,
                        text=f"AI error: {llm_response.message}",
                    )
                    return

                if isinstance(llm_response, TextResponse):
                    # LLM returned final response
                    yield OrchestratorEvent(
                        type=EventType.RESPONSE,
                        text=llm_response.text,
                    )
                    yield OrchestratorEvent(type=EventType.DONE)
                    return

                if isinstance(llm_response, ToolCallsResponse):
                    # LLM wants to call tools
                    # Add assistant message with tool_calls to history
                    # Convert LlmToolCall to ToolCall for storage
                    tool_calls_for_message = [
                        ToolCall(
                            id=tc.id,
                            name=tc.name,
                            arguments=tc.arguments,
                        )
                        for tc in llm_response.tool_calls
                    ]
                    messages.append(
                        ChatMessage(
                            role=MessageRole.ASSISTANT,
                            content="",
                            tool_calls=tool_calls_for_message,
                        )
                    )

                    # Execute each tool call
                    for tool_call in llm_response.tool_calls:
                        yield OrchestratorEvent(
                            type=EventType.TOOL_START,
                            name=tool_call.name,
                            args=tool_call.arguments,
                        )

                        try:
                            result = await self.mcp_client.call_tool(
                                tool_call.name,
                                tool_call.arguments,
                            )

                            # Extract text from result
                            result_text = "\n".join(
                                c.text for c in result.content if c.text
                            )

                            if result.is_error:
                                yield OrchestratorEvent(
                                    type=EventType.TOOL_ERROR,
                                    name=tool_call.name,
                                    result=result_text,
                                )
                            else:
                                yield OrchestratorEvent(
                                    type=EventType.TOOL_COMPLETE,
                                    name=tool_call.name,
                                    result=result_text,
                                )

                            # Add tool result to messages
                            messages.append(
                                ChatMessage(
                                    role=MessageRole.TOOL,
                                    content=result_text,
                                    tool_call_id=tool_call.id,
                                )
                            )

                        except Exception as e:
                            error_msg = f"Tool execution failed: {e}"
                            logger.error(error_msg)

                            yield OrchestratorEvent(
                                type=EventType.TOOL_ERROR,
                                name=tool_call.name,
                                result=error_msg,
                            )

                            # Add error as tool result
                            messages.append(
                                ChatMessage(
                                    role=MessageRole.TOOL,
                                    content=error_msg,
                                    tool_call_id=tool_call.id,
                                )
                            )

            # Max iterations reached
            yield OrchestratorEvent(
                type=EventType.ERROR,
                text="Maximum tool iterations reached. Please try again.",
            )

        except Exception as e:
            logger.exception(f"Orchestrator error: {e}")
            yield OrchestratorEvent(
                type=EventType.ERROR,
                text=f"An error occurred: {e}",
            )

    async def close(self) -> None:
        """Clean up resources."""
        await self.mcp_client.disconnect()
