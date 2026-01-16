"""Pydantic models for the chat backend."""
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel


class MessageRole(str, Enum):
    """Role of a message in the conversation."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class ChatMessage(BaseModel):
    """A message in the conversation."""
    role: MessageRole
    content: str
    tool_call_id: Optional[str] = None
    tool_calls: Optional[list["ToolCall"]] = None  # For assistant messages with tool calls


class ChatRequest(BaseModel):
    """Request to the chat endpoint."""
    message: str
    history: list[ChatMessage] = []


class ToolCall(BaseModel):
    """A tool call made by the LLM."""
    id: str
    name: str
    arguments: dict[str, Any]


class McpTool(BaseModel):
    """A tool available from the MCP server."""
    name: str
    description: Optional[str] = None
    input_schema: Optional[dict[str, Any]] = None


class McpContent(BaseModel):
    """Content returned from an MCP tool call."""
    type: str
    text: Optional[str] = None


class McpToolResult(BaseModel):
    """Result of an MCP tool call."""
    content: list[McpContent]
    is_error: bool = False


# SSE Event Types
class EventType(str, Enum):
    """Types of events sent to the client."""
    THINKING = "thinking"
    TOOL_START = "tool_start"
    TOOL_COMPLETE = "tool_complete"
    TOOL_ERROR = "tool_error"
    RESPONSE = "response"
    ERROR = "error"
    DONE = "done"


class OrchestratorEvent(BaseModel):
    """Event sent to the client during chat processing."""
    type: EventType
    text: Optional[str] = None
    name: Optional[str] = None  # Tool name
    args: Optional[dict[str, Any]] = None  # Tool arguments
    result: Optional[str] = None  # Tool result
