from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AttachmentSummary:
    display_name: str | None
    file_reference: str | None
    method: str | None
    size: int | None = None
    content_type: str | None = None


@dataclass(frozen=True)
class AttachmentFetchResult:
    content: bytes | None = None
    content_type: str | None = None
    display_name: str | None = None


@dataclass(frozen=True)
class FolderSummary:
    server_id: str
    parent_id: str
    display_name: str
    folder_type: str


@dataclass(frozen=True)
class FolderSyncResponse:
    sync_key: str
    folders: list[FolderSummary]


@dataclass(frozen=True)
class MessageSummary:
    server_id: str
    subject: str | None
    sender: str | None
    received_at: str | None
    attachments: list[AttachmentSummary]


@dataclass(frozen=True)
class MessageDetail:
    server_id: str
    subject: str | None = None
    sender: str | None = None
    received_at: str | None = None
    body: str | None = None
    attachments: list[AttachmentSummary] | None = None


@dataclass(frozen=True)
class SyncResponse:
    sync_key: str
    messages: list[MessageSummary]


@dataclass(frozen=True)
class ProvisionResponse:
    policy_key: str | None = None
    policy_data: Any | None = None
