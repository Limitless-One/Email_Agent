"""Gmail adapter: explicit label boundary, plain text extraction, threaded drafts."""

from __future__ import annotations

import base64
from email.mime.text import MIMEText
from email.utils import parseaddr
from pathlib import Path
from typing import Protocol

from .config import AgentConfig
from .contracts import IncomingMessage
from .text import newest_customer_text


class MailClient(Protocol):
    def candidates(self, limit: int) -> list[IncomingMessage]: ...
    def create_draft(self, message: IncomingMessage, body: str, run_id: str) -> str: ...
    def send_draft(self, draft_id: str) -> str: ...
    def sent_for_run(self, run_id: str) -> str | None: ...
    def complete(self, message_id: str) -> None: ...


class GmailApiClient:
    """Real client, constructed lazily so tests and offline evaluation need no OAuth."""

    SCOPES = ("https://www.googleapis.com/auth/gmail.modify", "https://www.googleapis.com/auth/gmail.send")

    def __init__(self, config: AgentConfig) -> None:
        self.config = config
        self._service = None
        self._labels: dict[str, str] | None = None

    @property
    def service(self):
        if self._service is not None:
            return self._service
        if not self.config.gmail_client_secret_path or not self.config.gmail_token_path:
            missing = []
            if not self.config.gmail_client_secret_path:
                missing.append("EMAIL_AGENT_GMAIL_CLIENT_SECRET_PATH")
            if not self.config.gmail_token_path:
                missing.append("EMAIL_AGENT_GMAIL_TOKEN_PATH")
            raise RuntimeError("Missing " + ", ".join(missing) + ". Set them in .env or export them in this shell.")
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
        creds = None
        token = Path(self.config.gmail_token_path)
        if token.exists():
            creds = Credentials.from_authorized_user_file(str(token), self.SCOPES)
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        if not creds or not creds.valid:
            flow = InstalledAppFlow.from_client_secrets_file(self.config.gmail_client_secret_path, self.SCOPES)
            creds = flow.run_local_server(port=0)
        token.parent.mkdir(parents=True, exist_ok=True)
        token.write_text(creds.to_json(), encoding="utf-8")
        self._service = build("gmail", "v1", credentials=creds, cache_discovery=False)
        return self._service

    def _label_ids(self) -> dict[str, str]:
        if self._labels is None:
            response = self.service.users().labels().list(userId="me").execute()
            self._labels = {item["name"]: item["id"] for item in response.get("labels", [])}
            if self.config.gmail_label not in self._labels:
                raise RuntimeError(f"Required Gmail label {self.config.gmail_label!r} does not exist")
            if self.config.done_label not in self._labels:
                created = self.service.users().labels().create(userId="me", body={"name": self.config.done_label}).execute()
                self._labels[self.config.done_label] = created["id"]
        return self._labels

    def candidates(self, limit: int) -> list[IncomingMessage]:
        self._label_ids()
        query = f'label:{self.config.gmail_label} is:unread -from:me'
        response = self.service.users().messages().list(userId="me", q=query, maxResults=limit).execute()
        return [self._get_message(item["id"]) for item in response.get("messages", [])]

    def _get_message(self, message_id: str) -> IncomingMessage:
        raw = self.service.users().messages().get(userId="me", id=message_id, format="full").execute()
        headers = {h["name"].lower(): h["value"] for h in raw["payload"].get("headers", [])}
        sender = parseaddr(headers.get("from", ""))[1].lower()
        recipients = [parseaddr(value)[1] for value in headers.get("to", "").split(",") if parseaddr(value)[1]]
        body = _plain_text(raw["payload"])
        return IncomingMessage(message_id=raw["id"], thread_id=raw["threadId"], sender=sender,
            recipients=recipients, subject=headers.get("subject", "(No subject)"), text=newest_customer_text(body),
            message_reference=headers.get("message-id"), references=headers.get("references"))

    def create_draft(self, message: IncomingMessage, body: str, run_id: str) -> str:
        reply = MIMEText(body, _charset="utf-8")
        reply["To"] = message.sender
        reply["Subject"] = message.subject if message.subject.lower().startswith("re:") else f"Re: {message.subject}"
        reply["X-NovaGear-Run-ID"] = run_id
        if message.message_reference:
            reply["In-Reply-To"] = message.message_reference
            reply["References"] = " ".join(filter(None, [message.references, message.message_reference]))
        raw = base64.urlsafe_b64encode(reply.as_bytes()).decode("ascii")
        draft = self.service.users().drafts().create(userId="me", body={"message": {"raw": raw, "threadId": message.thread_id}}).execute()
        return draft["id"]

    def send_draft(self, draft_id: str) -> str:
        sent = self.service.users().drafts().send(userId="me", body={"id": draft_id}).execute()
        return sent["id"]

    def sent_for_run(self, run_id: str) -> str | None:
        # Gmail search does not guarantee custom-header indexing, so inspect a small Sent page after an ambiguous send.
        page = self.service.users().messages().list(userId="me", q="in:sent", maxResults=50).execute()
        for item in page.get("messages", []):
            message = self.service.users().messages().get(userId="me", id=item["id"], format="metadata",
                metadataHeaders=["X-NovaGear-Run-ID"]).execute()
            headers = message.get("payload", {}).get("headers", [])
            if any(header.get("value") == run_id for header in headers):
                return message["id"]
        return None

    def complete(self, message_id: str) -> None:
        labels = self._label_ids()
        self.service.users().messages().modify(userId="me", id=message_id,
            body={"removeLabelIds": ["UNREAD", labels[self.config.gmail_label]], "addLabelIds": [labels[self.config.done_label]]}).execute()


def _plain_text(part: dict) -> str:
    """Recursively return only non-attachment text/plain parts; HTML is deliberately ignored."""
    if part.get("filename"):
        return ""
    if part.get("mimeType") == "text/plain":
        data = part.get("body", {}).get("data", "")
        return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", errors="replace") if data else ""
    return "\n".join(filter(None, (_plain_text(child) for child in part.get("parts", []))))
