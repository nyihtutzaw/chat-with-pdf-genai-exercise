"""Package for application configuration."""

from .config import Settings, init_db
from .cors import setup_cors

# Create a single settings instance that can be imported throughout the app
settings = Settings()

__all__ = ["settings", "setup_cors", "init_db"]

