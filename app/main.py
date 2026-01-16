"""FastAPI application with SSE streaming endpoint."""
import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.config import settings
from app.models import ChatRequest, OrchestratorEvent
from app.orchestrator import ChatOrchestrator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Global orchestrator instance
orchestrator: ChatOrchestrator = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan - startup and shutdown."""
    global orchestrator

    # Startup
    logger.info("Starting Rail Chatbot Backend...")

    # Validate settings
    try:
        settings.validate()
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        raise

    orchestrator = ChatOrchestrator()
    logger.info("Backend started successfully")

    yield

    # Shutdown
    logger.info("Shutting down...")
    if orchestrator:
        await orchestrator.close()


app = FastAPI(
    title="Rail Chatbot Backend",
    description="Backend server for Rail Chatbot - handles AI and MCP tool calls",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "rail-chatbot-backend"}


@app.post("/api/chat")
async def chat(request: ChatRequest):
    """
    Process a chat message and stream events via SSE.

    Request body:
    {
        "message": "Find trains from Delhi to Mumbai",
        "history": []
    }

    Response: Server-Sent Events stream with OrchestratorEvent objects
    """
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Service not ready")

    async def event_generator():
        """Generate SSE events from the orchestrator."""
        try:
            async for event in orchestrator.process_message(
                request.message, request.history
            ):
                # Format as SSE
                event_json = event.model_dump_json()
                yield f"data: {event_json}\n\n"

        except Exception as e:
            logger.exception(f"Error in event generator: {e}")
            error_event = OrchestratorEvent(
                type="error",
                text=f"Server error: {e}",
            )
            yield f"data: {error_event.model_dump_json()}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@app.get("/api/tools")
async def list_tools():
    """List available MCP tools (for debugging)."""
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Service not ready")

    try:
        await orchestrator.mcp_client.initialize()
        tools = await orchestrator.mcp_client.list_tools()
        return {
            "count": len(tools),
            "tools": [
                {"name": t.name, "description": t.description}
                for t in tools
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
    )
