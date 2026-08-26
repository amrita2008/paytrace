"""PayTrace application configuration.

All configuration is loaded from environment variables.
No secrets are hardcoded. No secrets appear in logs or API responses.
"""

import os


class Settings:
    """Application settings loaded from environment variables.

    Phase 1A: contains only application and server settings.
    Sensitive credentials (API keys, tokens) will be introduced
    in the phases that require them (e.g., AI investigation layer).
    """

    # Application
    APP_NAME: str = "PayTrace"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = os.getenv("PAYTRACE_DEBUG", "false").lower() == "true"

    # Server
    HOST: str = os.getenv("PAYTRACE_HOST", "127.0.0.1")
    PORT: int = int(os.getenv("PAYTRACE_PORT", "8000"))

    # Data paths (relative to project root — not exposed via API)
    DATA_DIR: str = os.getenv("PAYTRACE_DATA_DIR", "data")
    EVALUATION_DIR: str = os.getenv("PAYTRACE_EVALUATION_DIR", "evaluation")


settings = Settings()
