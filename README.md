# Rail Chatbot Backend

Python FastAPI backend server for the Rail Chatbot Android app. Handles AI orchestration and MCP (Model Context Protocol) integration with Indian Railways API.

## Architecture

```
Android App (UI) ──HTTP/SSE──▶ This Backend ──▶ Railway MCP + OpenAI
```

The Android app is a thin UI client that streams responses from this backend server. All API keys and AI logic are kept server-side for security.

## Features

- **SSE Streaming**: Real-time chat responses via Server-Sent Events
- **MCP Integration**: Connects to Railway API via RapidAPI MCP server
- **OpenAI Tool Calling**: GPT-4 with function calling for railway queries
- **Docker Support**: Easy deployment with Docker Compose

## API Endpoints

### POST /api/chat

Stream chat responses for a user message.

**Request:**
```json
{
  "message": "Find trains from Delhi to Mumbai",
  "history": [
    {"role": "user", "content": "Hi"},
    {"role": "assistant", "content": "Hello!"}
  ]
}
```

**Response:** Server-Sent Events stream
```
data: {"type": "thinking", "text": "Analyzing your request..."}
data: {"type": "tool_start", "name": "TrainsBetweenStations", "args": {...}}
data: {"type": "tool_complete", "name": "TrainsBetweenStations", "result": "..."}
data: {"type": "response", "text": "Here are the trains..."}
data: {"type": "done"}
```

### GET /health

Health check endpoint. Returns `{"status": "healthy"}`.

## Setup

### Prerequisites

- Python 3.11+
- OpenAI API key
- RapidAPI key (for IRCTC API access)

### Local Development

1. Clone the repository:
   ```bash
   git clone https://github.com/nasirperwez/rail-chatbot-backend.git
   cd rail-chatbot-backend
   ```

2. Create virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

5. Run the server:
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

### Docker Deployment

1. Configure environment:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

2. Build and run:
   ```bash
   docker-compose up --build
   ```

The server will be available at `http://localhost:8000`.

## Environment Variables

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | OpenAI API key for GPT-4 |
| `RAPIDAPI_KEY` | RapidAPI key for IRCTC API |
| `RAPIDAPI_HOST` | RapidAPI host (default: `irctc1.p.rapidapi.com`) |
| `MCP_SERVER_URL` | MCP server URL (default: `https://mcp.rapidapi.com`) |
| `OPENAI_MODEL` | OpenAI model (default: `gpt-4o-mini`) |

## Project Structure

```
rail-chatbot-backend/
├── app/
│   ├── __init__.py
│   ├── main.py           # FastAPI app, SSE endpoint
│   ├── config.py         # Environment configuration
│   ├── models.py         # Pydantic data models
│   ├── orchestrator.py   # AI + MCP tool calling loop
│   ├── mcp_client.py     # MCP JSON-RPC client
│   └── llm_client.py     # OpenAI client
├── .env.example          # Environment template
├── requirements.txt      # Python dependencies
├── Dockerfile
└── docker-compose.yml
```

## Testing

Test with curl:
```bash
curl -N -X POST "http://localhost:8000/api/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "Check PNR status 1234567890"}'
```

## Related

- [Rail Chatbot Android App](https://github.com/nasirperwez/RailAndroidboat) - Android client for this backend

## License

MIT
