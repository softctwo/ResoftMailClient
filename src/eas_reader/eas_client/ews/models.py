from dataclasses import dataclass


@dataclass(frozen=True)
class EwsItemSummary:
    item_id: str
    change_key: str | None
    subject: str | None
    sender: str | None
    received_at: str | None
    has_attachments: bool


@dataclass(frozen=True)
class EwsFindItemsResponse:
    items: list[EwsItemSummary]


@dataclass(frozen=True)
class EwsAttachmentSummary:
    attachment_id: str
    name: str | None
    content_type: str | None
    size: int | None
    is_inline: bool


@dataclass(frozen=True)
class EwsItemDetail:
    item_id: str
    change_key: str | None
    subject: str | None
    body: str | None
    attachments: list[EwsAttachmentSummary]


@dataclass(frozen=True)
class EwsAttachmentContent:
    attachment_id: str
    name: str | None
    content_type: str | None
    content: bytes
