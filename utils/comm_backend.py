# utils/comm_backend.py
# Explanation:
# Build a tiny communication backend exposing `.email` for MasterWorkflowAgent.
# It reads from your nested settings structure: settings.smtp.{host,port,username,password,sender,secure,starttls}.

from types import SimpleNamespace
from config.config import settings
from utils.email_agent import EmailAgent


def build_comm_backend():
    """
    Create a tiny backend exposing `.email` used by agents.
    The function expects a nested settings.smtp.* structure.
    """
    smtp = settings.smtp  # <- your existing nested config object

    # Validate required fields early for clear error messages.
    required = ("host", "port", "username", "password", "sender")
    missing = [k for k in required if not getattr(smtp, k, None)]
    if missing:
        raise RuntimeError(f"Incomplete SMTP config: missing {', '.join(missing)}")

    # Instantiate your existing EmailAgent. If your EmailAgent signature differs,
    # adapt the keyword names here to match utils/email_agent.py.
    email_agent = EmailAgent(
        host=smtp.host,  # e.g. "smtp.example.com"
        port=int(smtp.port),  # e.g. 465 or 587
        username=smtp.username,  # login
        password=smtp.password,  # secret
        sender=smtp.sender,  # visible From:
        use_tls=getattr(smtp, "secure", True),  # bool; defaults to True if not present
        # If your EmailAgent uses `starttls` instead of `use_tls`, adjust accordingly:
        # starttls=getattr(smtp, "starttls", False),
    )

    # Return a simple container compatible with agents expecting `.email`.
    return SimpleNamespace(email=email_agent)
