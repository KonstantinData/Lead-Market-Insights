# ================================================================
# File: interfaces/email.py
# Purpose: Define the abstract interface (port) for sending emails.
# This interface allows any email transport (e.g., SMTP, API, mock)
# to plug into the application without changing core business logic.
# ================================================================

from typing import Mapping, Optional, Any, Protocol


class IEmailSender(Protocol):
    """
    Interface for an asynchronous email sender.

    Any concrete adapter (SMTP, API, Mock, etc.) must implement this interface.
    It defines a single asynchronous `send()` method which is used by higher-level
    agents (e.g., HumanInLoopAgent) to deliver outgoing messages.

    Implementations are responsible for:
    - establishing and managing transport (SMTP, HTTP, etc.)
    - handling authentication and connection lifecycle
    - returning a result or raising a well-defined exception
    """

    async def send(
        self,
        to: str,
        subject: str,
        body: str,
        *,
        headers: Optional[Mapping[str, str]] = None,
    ) -> Any:
        """
        Send an email asynchronously.

        Args:
            to (str): Recipient email address.
            subject (str): Subject line of the email.
            body (str): Plain-text (or HTML) body content.
            headers (Optional[Mapping[str, str]]): Additional headers for correlation,
                such as X-Run-ID or X-HITL markers.

        Returns:
            Any: Transport-specific result (e.g., message ID or delivery response).

        Raises:
            Exception: Should raise on connection errors, authentication failures,
                       or invalid message payloads.
        """
        ...
