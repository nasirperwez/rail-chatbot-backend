"""MCP Client for communicating with the Railway MCP server via JSON-RPC 2.0."""
import logging
from typing import Any, Optional
import httpx

from app.config import settings
from app.models import McpTool, McpToolResult, McpContent

logger = logging.getLogger(__name__)


class McpException(Exception):
    """Exception for MCP protocol errors."""

    def __init__(self, code: int, message: str):
        self.code = code
        super().__init__(message)


class McpClient:
    """
    Client for communicating with the MCP server.
    Implements JSON-RPC 2.0 protocol over HTTP.
    """

    CLIENT_NAME = "RailChatbotBackend"
    CLIENT_VERSION = "1.0.0"

    def __init__(self):
        self._request_id = 0
        self._is_initialized = False
        self._session_id: Optional[str] = None
        self._cached_tools: list[McpTool] = []
        self._http_client = httpx.AsyncClient(timeout=60.0)

    async def initialize(self) -> None:
        """Initialize connection to the MCP server."""
        if self._is_initialized:
            logger.debug("MCP client already initialized")
            return

        params = {
            "protocolVersion": settings.MCP_PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "clientInfo": {
                "name": self.CLIENT_NAME,
                "version": self.CLIENT_VERSION,
            },
        }

        response = await self._send_request("initialize", params)

        if "error" in response:
            raise McpException(
                response["error"].get("code", -1),
                response["error"].get("message", "Unknown error"),
            )

        # Send initialized notification
        await self._send_notification("notifications/initialized")

        self._is_initialized = True
        logger.info("MCP client initialized successfully")

    async def list_tools(self) -> list[McpTool]:
        """List available tools from the MCP server."""
        await self._ensure_initialized()

        if self._cached_tools:
            return self._cached_tools

        response = await self._send_request("tools/list", None)

        if "error" in response:
            raise McpException(
                response["error"].get("code", -1),
                response["error"].get("message", "Unknown error"),
            )

        result = response.get("result", {})
        tools_array = result.get("tools", [])

        self._cached_tools = [
            McpTool(
                name=tool.get("name", ""),
                description=tool.get("description"),
                input_schema=tool.get("inputSchema"),
            )
            for tool in tools_array
        ]

        logger.info(f"Fetched {len(self._cached_tools)} tools")
        return self._cached_tools

    async def call_tool(
        self, name: str, arguments: dict[str, Any]
    ) -> McpToolResult:
        """Call a tool on the MCP server."""
        await self._ensure_initialized()

        # Convert arguments to strings where needed (MCP expects strings)
        string_args = {
            k: str(v) if v is not None else None for k, v in arguments.items()
        }

        params = {"name": name, "arguments": string_args}

        logger.info(f"Calling tool: {name} with args: {arguments}")

        response = await self._send_request("tools/call", params)

        if "error" in response:
            raise McpException(
                response["error"].get("code", -1),
                response["error"].get("message", "Unknown error"),
            )

        result = response.get("result", {})
        content_array = result.get("content", [])

        contents = [
            McpContent(
                type=content.get("type", "text"),
                text=content.get("text"),
            )
            for content in content_array
        ]

        is_error = result.get("isError", False)

        return McpToolResult(content=contents, is_error=is_error)

    def is_connected(self) -> bool:
        """Check if the client is connected and initialized."""
        return self._is_initialized

    async def disconnect(self) -> None:
        """Disconnect and reset the client."""
        self._is_initialized = False
        self._session_id = None
        self._cached_tools = []
        await self._http_client.aclose()

    async def _ensure_initialized(self) -> None:
        """Ensure the client is initialized before making requests."""
        if not self._is_initialized:
            await self.initialize()

    async def _send_request(
        self, method: str, params: Optional[dict[str, Any]]
    ) -> dict[str, Any]:
        """Send a JSON-RPC request to the MCP server."""
        self._request_id += 1

        request_body = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
        }
        if params is not None:
            request_body["params"] = params

        headers = {
            "Content-Type": "application/json",
            "x-api-host": settings.RAPIDAPI_HOST,
            "x-api-key": settings.RAPIDAPI_KEY,
            "MCP-Protocol-Version": settings.MCP_PROTOCOL_VERSION,
        }
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id

        logger.debug(f"Sending MCP request: {method}")

        response = await self._http_client.post(
            settings.MCP_SERVER_URL,
            json=request_body,
            headers=headers,
        )

        response_data = response.json()
        logger.debug(f"MCP response: {response_data}")

        return response_data

    async def _send_notification(self, method: str) -> None:
        """Send a JSON-RPC notification to the MCP server."""
        request_body = {
            "jsonrpc": "2.0",
            "method": method,
        }

        headers = {
            "Content-Type": "application/json",
            "x-api-host": settings.RAPIDAPI_HOST,
            "x-api-key": settings.RAPIDAPI_KEY,
            "MCP-Protocol-Version": settings.MCP_PROTOCOL_VERSION,
        }
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id

        try:
            await self._http_client.post(
                settings.MCP_SERVER_URL,
                json=request_body,
                headers=headers,
            )
        except Exception as e:
            logger.warning(f"Failed to send notification: {e}")
