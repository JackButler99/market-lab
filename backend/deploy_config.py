"""Deployment configuration and authorization. No secret is returned to API clients."""

import hmac
import os
from pathlib import Path


def production():
    return os.getenv("MARKET_ENV", "development").lower() == "production"


def database_path():
    configured = os.getenv("DATABASE_PATH", "").strip()
    if production() and (not configured or not Path(configured).is_absolute()):
        raise ValueError("Production requires an absolute DATABASE_PATH on a persistent disk")
    return Path(configured) if configured else Path(__file__).parent / "data" / "research.sqlite3"


def validate():
    if production():
        token = os.getenv("API_ACCESS_TOKEN", "")
        if len(token) < 32 or token.lower().startswith(("your", "replace", "changeme")):
            raise ValueError("Set a strong API_ACCESS_TOKEN of at least 32 characters")
        if not database_path().parent.is_dir():
            raise ValueError("Persistent database directory does not exist; check the disk mount")
    return os.getenv("HOST", "0.0.0.0" if production() else "127.0.0.1"), int(
        os.getenv("PORT", "8000")
    )


def authorized(headers, path):
    if not production() or path.split("?", 1)[0] == "/health":
        return True
    token = os.getenv("API_ACCESS_TOKEN", "")
    if len(token) < 32:
        return False
    return hmac.compare_digest(
        headers.get("Authorization", "").encode("utf-8"), ("Bearer " + token).encode("utf-8")
    )


def cors(origin):
    default = "" if production() else "http://localhost:3000"
    allowed = {s.strip() for s in os.getenv("ALLOWED_ORIGINS", default).split(",") if s.strip()}
    result = {"Vary": "Origin"}
    if origin and origin in allowed and origin != "null":
        result.update(
            {
                "Access-Control-Allow-Origin": origin,
                "Access-Control-Allow-Headers": "Content-Type, Authorization",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            }
        )
    return result
