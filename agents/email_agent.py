import logging
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Iterable, Optional, Sequence, Union

from utils.async_http import run_async
from utils.async_smtp import send_email_ssl


class EmailAgent:
    """
    Central agent for all email workflows (request, reminder, escalation).
    SMTP configuration is set during instantiation.
    """

    def __init__(self, smtp_server, smtp_port, username, password, sender_email):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.sender_email = sender_email

    async def send_email_async(
        self,
        recipient,
        subject,
        body,
        html_body=None,
        *,
        attachments: Optional[Sequence[Union[str, Path]]] = None,
        attachment_links: Optional[Iterable[str]] = None,
    ):
        """
        Sends an email. Optionally, an HTML body can be provided.
        """
        msg = MIMEMultipart()
        msg["From"] = self.sender_email
        msg["To"] = recipient
        msg["Subject"] = subject

        normalized_links = self._normalize_links(attachment_links)
        text_body = self._augment_plain_body(body, normalized_links)
        html_body = self._augment_html_body(html_body, normalized_links)

        alternative_part = MIMEMultipart("alternative")
        alternative_part.attach(MIMEText(text_body, "plain"))
        if html_body:
            alternative_part.attach(MIMEText(html_body, "html"))
        msg.attach(alternative_part)

        for attachment_part in self._build_attachments(attachments):
            msg.attach(attachment_part)

        try:
            await send_email_ssl(
                host=self.smtp_server,
                username=self.username,
                password=self.password,
                port=self.smtp_port,
                message=msg.as_string(),
                to_addrs=[recipient],
            )
            logging.info(f"Email sent to {recipient} with subject '{subject}'")
            return True
        except Exception as e:
            logging.error(f"Failed to send email to {recipient}: {e}")
            return False

    def send_email(
        self,
        recipient,
        subject,
        body,
        html_body=None,
        *,
        attachments: Optional[Sequence[Union[str, Path]]] = None,
        attachment_links: Optional[Iterable[str]] = None,
    ):
        """Synchronous facade that dispatches to the async implementation."""

        return run_async(
            self.send_email_async(
                recipient,
                subject,
                body,
                html_body,
                attachments=attachments,
                attachment_links=attachment_links,
            )
        )

    def _normalize_links(self, links: Optional[Iterable[str]]) -> Sequence[str]:
        if not links:
            return []
        normalized = []
        for link in links:
            if not link:
                continue
            normalized.append(str(link).strip())
        return normalized

    def _augment_plain_body(self, body: str, links: Sequence[str]) -> str:
        if not links:
            return body
        clean_body = body.rstrip()
        link_lines = ["", "", "Access the dossier using the following link(s):"]
        link_lines.extend(f"- {link}" for link in links)
        return clean_body + "\n".join(link_lines) + "\n"

    def _augment_html_body(
        self, html_body: Optional[str], links: Sequence[str]
    ) -> Optional[str]:
        if not links or html_body is None:
            return html_body
        link_items = "".join(
            f'<li><a href="{link}">{link}</a></li>' for link in links
        )
        link_block = (
            "<hr><p>Access the dossier using the following link(s):</p>"
            f"<ul>{link_items}</ul>"
        )
        if "</body>" in html_body:
            return html_body.replace("</body>", f"{link_block}</body>")
        return html_body + link_block

    def _build_attachments(
        self, attachments: Optional[Sequence[Union[str, Path]]]
    ) -> Sequence[MIMEApplication]:
        prepared: list[MIMEApplication] = []
        if not attachments:
            return prepared

        for attachment in attachments:
            if attachment is None:
                continue
            path = Path(attachment)
            try:
                data = path.read_bytes()
            except OSError as exc:
                logging.error("Unable to read attachment %s: %s", path, exc)
                continue

            part = MIMEApplication(
                data, _subtype=path.suffix.lstrip(".") or "octet-stream"
            )
            part.add_header("Content-Disposition", "attachment", filename=path.name)
            prepared.append(part)
        return prepared


# Example usage:
# agent = EmailAgent("smtp.example.com", 465, "user", "pass",
# "noreply@example.com")
# agent.send_email("recipient@example.com", "Subject", "Body")
