"""Safe, auditable email support worker for the NovaGear prototype."""

from .config import AgentConfig
from .worker import EmailAgentWorker

__all__ = ["AgentConfig", "EmailAgentWorker"]
