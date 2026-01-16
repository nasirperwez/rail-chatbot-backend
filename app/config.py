"""Configuration management using environment variables."""
import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()


class Settings:
    """Application settings loaded from environment variables."""

    # OpenAI Configuration
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    # MCP / RapidAPI Configuration
    RAPIDAPI_KEY: str = os.getenv("RAPIDAPI_KEY", "")
    RAPIDAPI_HOST: str = os.getenv("RAPIDAPI_HOST", "irctc1.p.rapidapi.com")
    MCP_SERVER_URL: str = os.getenv("MCP_SERVER_URL", "https://mcp.rapidapi.com")
    MCP_PROTOCOL_VERSION: str = "2025-03-26"

    # Server Configuration
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))

    def validate(self) -> bool:
        """Validate that required settings are present."""
        if not self.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        if not self.RAPIDAPI_KEY:
            raise ValueError("RAPIDAPI_KEY environment variable is required")
        return True


settings = Settings()
