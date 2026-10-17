"""Configuration is environment-only; no API key or credential path is committed."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


def _bool(value: str | None, default: bool = False) -> bool:
    return default if value is None else value.lower() in {"1", "true", "yes"}


def load_dotenv(path: Path = Path(".env")) -> None:
    """Load simple KEY=VALUE pairs without replacing variables supplied by the shell."""
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key.startswith("EMAIL_AGENT_") and key not in os.environ:
            os.environ[key] = value


@dataclass(frozen=True)
class AgentConfig:
    state_db_path: Path = Path("agent_state.db")
    gmail_label: str = "AI_PROCESS"
    done_label: str = "AI_DONE"
    own_email: str = ""
    allowed_sender_domain: str = ""
    max_body_chars: int = 12_000
    batch_size: int = 10
    poll_seconds: int = 90
    send_enabled: bool = False
    min_confidence: float = 0.80
    model_provider: str = "rule_based"
    model_name: str = ""
    model_api_key: str = ""
    model_base_url: str = ""
    gmail_client_secret_path: str = ""
    gmail_token_path: str = ""
    debug_artifacts: bool = False

    @classmethod
    def from_env(cls) -> "AgentConfig":
        load_dotenv()
        env = os.environ
        return cls(
            state_db_path=Path(env.get("EMAIL_AGENT_STATE_DB", "agent_state.db")),
            gmail_label=env.get("EMAIL_AGENT_GMAIL_LABEL", "AI_PROCESS"),
            done_label=env.get("EMAIL_AGENT_DONE_LABEL", "AI_DONE"),
            own_email=env.get("EMAIL_AGENT_OWN_EMAIL", "").lower(),
            allowed_sender_domain=env.get("EMAIL_AGENT_ALLOWED_SENDER_DOMAIN", "").lower(),
            max_body_chars=int(env.get("EMAIL_AGENT_MAX_BODY_CHARS", "12000")),
            batch_size=int(env.get("EMAIL_AGENT_BATCH_SIZE", "10")),
            poll_seconds=int(env.get("EMAIL_AGENT_POLL_SECONDS", "90")),
            send_enabled=_bool(env.get("EMAIL_AGENT_SEND_ENABLED")),
            min_confidence=float(env.get("EMAIL_AGENT_MIN_CONFIDENCE", "0.80")),
            model_provider=env.get("EMAIL_AGENT_MODEL_PROVIDER", "rule_based").lower(),
            model_name=env.get("EMAIL_AGENT_MODEL", ""),
            model_api_key=env.get("EMAIL_AGENT_MODEL_API_KEY", ""),
            model_base_url=env.get("EMAIL_AGENT_MODEL_BASE_URL", ""),
            gmail_client_secret_path=env.get("EMAIL_AGENT_GMAIL_CLIENT_SECRET_PATH", ""),
            gmail_token_path=env.get("EMAIL_AGENT_GMAIL_TOKEN_PATH", ""),
            debug_artifacts=_bool(env.get("EMAIL_AGENT_DEBUG_ARTIFACTS")),
        )
