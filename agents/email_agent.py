# =====================================================================
# File: utils/email_agent.py
# Purpose: Central agent for all email workflows (request, reminder,
#          escalation) in the Lead-Market-Insights system.
# Implements:
#   • ADR-0004 – Config Compatibility for Nested SMTP Settings
#   • ADR-0005 – Async EmailAgent consistency
# =====================================================================

import logging
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Iterable, Optional, Sequence, Union

from utils.async_smtp import send_email_ssl


# ------------------------------------------------------------
# SMTP Configuration Validation
# ------------------------------------------------------------
def _validate_smtp_settings(settings: object) -> None:
    """
    Ensure SMTP configuration is complete before attempting to send mail.

    Compatible with both:
      - Flat schema:  settings.smtp_host, settings.smtp_username, ...
      - Nested schema: settings.smtp.host, settings.smtp.username, ...
    """

    def _normalize(value: Optional[object]) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return str(value)

    # Compatibility layer
    smtp = getattr(settings, "smtp", settings)

    host = _normalize(getattr(smtp, "host", getattr(settings, "smtp_host", None)))
    port_value = getattr(smtp, "port", getattr(settings, "smtp_port", None))
    username = _normalize(
        getattr(smtp, "username", getattr(settings, "smtp_username", None))
        or getattr(smtp, "user", getattr(settings, "smtp_user", None))
    )
    password = _normalize(
        getattr(smtp, "password", getattr(settings, "smtp_password", None))
    )
    sender = _normalize(
        getattr(smtp, "sender", getattr(settings, "smtp_sender", None))
        or getattr(smtp, "from_addr", getattr(settings, "smtp_from", None))
    )

    missing: list[str] = []

    if not host:
        missing.append("smtp_host")
    try:
        port = int(port_value)
        if port <= 0:
            missing.append("smtp_port")
    except (TypeError, ValueError):
        missing.append("smtp_port")
    if not username:
        missing.append("smtp_username")
    if not password:
        missing.append("smtp_password")

    # Default sender heuristic
    if not sender and username and "@" in username:
        sender = username
        try:
            setattr(settings, "smtp_sender", sender)
        except Exception:
            pass
    if not sender:
        missing.append("smtp_sender")

    # Raise if incomplete
    if missing:
        unique_missing = sorted(set(missing))
        raise RuntimeError(
            "SMTP configuration incomplete: " + ", ".join(unique_missing)
        )

    logging.info(
        f"[SMTP Validation] OK: host={host}, port={port}, sender={sender}, user={username}"
    )


# ------------------------------------------------------------
# Email Agent
# ------------------------------------------------------------
class EmailAgent:
    """
    Central async email agent used by all agents (HITL, reminders, etc.).
    Handles plain text, HTML, attachments, and link augmentation.
    """

    def __init__(self, smtp_server, smtp_port, username, password, sender_email):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.sender_email = sender_email

    # ------------------------
    # Public API
    # ------------------------
    async def send_email_async(
        self,
        recipient: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        *,
        attachments: Optional[Sequence[Union[str, Path]]] = None,
        attachment_links: Optional[Iterable[str]] = None,
    ) -> bool:
        """Send an email with optional HTML body, attachments, and links."""
        msg = MIMEMultipart()
        msg["From"] = self.sender_email
        msg["To"] = recipient
        msg["Subject"] = subject

        normalized_links = self._normalize_links(attachment_links)
        text_body = self._augment_plain_body(body, normalized_links)
        html_body = self._augment_html_body(html_body, normalized_links)

        alt = MIMEMultipart("alternative")
        alt.attach(MIMEText(text_body, "plain"))
        if html_body:
            alt.attach(MIMEText(html_body, "html"))
        msg.attach(alt)

        for part in self._build_attachments(attachments):
            msg.attach(part)

        try:
            await send_email_ssl(
                host=self.smtp_server,
                username=self.username,
                password=self.password,
                port=self.smtp_port,
                message=msg.as_string(),
                to_addrs=[recipient],
            )
            logging.info(f"[EmailAgent] Email sent → {recipient} | Subject: {subject}")
            return True
        except Exception as e:
            logging.error(f"[EmailAgent] Failed to send email → {recipient}: {e}")
            return False

    # ------------------------
    # Internal Helpers
    # ------------------------
    def _normalize_links(self, links: Optional[Iterable[str]]) -> Sequence[str]:
        return [str(l).strip() for l in links or [] if l]

    def _augment_plain_body(self, body: str, links: Sequence[str]) -> str:
        if not links:
            return body
        body = body.rstrip() + "\n\nAccess the dossier via:\n"
        return body + "\n".join(f"- {link}" for link in links) + "\n"

    def _augment_html_body(
        self, html_body: Optional[str], links: Sequence[str]
    ) -> Optional[str]:
        if not html_body or not links:
            return html_body
        link_items = "".join(f'<li><a href="{l}">{l}</a></li>' for l in links)
        link_block = f"<hr><p>Access the dossier:</p><ul>{link_items}</ul>"
        return (
            html_body.replace("</body>", f"{link_block}</body>")
            if "</body>" in html_body
            else html_body + link_block
        )

    def _build_attachments(
        self, attachments: Optional[Sequence[Union[str, Path]]]
    ) -> Sequence[MIMEApplication]:
        built: list[MIMEApplication] = []
        for att in attachments or []:
            path = Path(att)
            try:
                data = path.read_bytes()
            except OSError as exc:
                logging.error(f"[EmailAgent] Could not read attachment {path}: {exc}")
                continue
            part = MIMEApplication(
                data, _subtype=path.suffix.lstrip(".") or "octet-stream"
            )
            part.add_header("Content-Disposition", "attachment", filename=path.name)
            built.append(part)
        return built
