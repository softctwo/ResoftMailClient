from dataclasses import dataclass


@dataclass(frozen=True)
class AttachmentSummary:
    display_name: str | None
    file_reference: str | None
    method: str | None
    size: int | None = None
    content_type: str | None = None


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
class SyncResponse:
    sync_key: str
    messages: list[MessageSummary]


@dataclass(frozen=True)
class MessageDetail:
    collection_id: str
    server_id: str
    subject: str | None
    sender: str | None
    to: str | None
    received_at: str | None
    body: str | None
    body_type: str | None
    attachments: list[AttachmentSummary]


@dataclass(frozen=True)
class AttachmentFetchResult:
    file_reference: str | None
    content_type: str | None
    data: bytes


@dataclass(frozen=True)
class ProvisionResponse:
    status: str
    policy_type: str | None
    policy_key: str | None
    settings: dict[str, str]
