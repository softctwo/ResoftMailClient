from eas_reader.eas.models import (
    AttachmentSummary,
    FolderSummary,
    FolderSyncResponse,
    MessageSummary,
    SyncResponse,
)
from eas_reader.wbxml import WbxmlElement, WbxmlText, decode_document


def parse_folder_sync_response(payload: bytes) -> FolderSyncResponse:
    root = decode_document(payload).root
    _require_tag(root, "FolderSync")
    _require_success_status(root, response_name="FolderSync")

    sync_key = _require_child_text(root, "SyncKey")
    changes = _find_child(root, "Changes")
    folders = [
        _parse_folder_summary(child)
        for child in (changes.children if changes is not None else [])
        if isinstance(child, WbxmlElement) and child.tag in {"Add", "Update"}
    ]

    return FolderSyncResponse(sync_key=sync_key, folders=folders)


def parse_sync_response(payload: bytes) -> SyncResponse:
    root = decode_document(payload).root
    _require_tag(root, "Sync")

    collections = _require_child(root, "Collections")
    collection = _require_child(collections, "Collection")
    _require_success_status(collection, response_name="Sync")
    sync_key = _require_child_text(collection, "SyncKey")
    commands = _find_child(collection, "Commands")
    messages = [
        _parse_message_summary(child)
        for child in (commands.children if commands is not None else [])
        if isinstance(child, WbxmlElement) and child.tag in {"Add", "Change"}
    ]

    return SyncResponse(sync_key=sync_key, messages=messages)


def _parse_folder_summary(element: WbxmlElement) -> FolderSummary:
    return FolderSummary(
        server_id=_require_child_text(element, "ServerId"),
        parent_id=_require_child_text(element, "ParentId"),
        display_name=_require_child_text(element, "DisplayName"),
        folder_type=_require_child_text(element, "Type"),
    )


def _parse_message_summary(element: WbxmlElement) -> MessageSummary:
    application_data = _require_child(element, "ApplicationData")
    return MessageSummary(
        server_id=_require_child_text(element, "ServerId"),
        subject=_optional_child_text(application_data, "Subject"),
        sender=_optional_child_text(application_data, "From"),
        received_at=_optional_child_text(application_data, "DateReceived"),
        attachments=_parse_attachments(application_data),
    )


def _parse_attachments(application_data: WbxmlElement) -> list[AttachmentSummary]:
    attachments = _find_child(application_data, "Attachments")
    if attachments is None:
        return []

    return [
        AttachmentSummary(
            display_name=_optional_child_text(child, "DisplayName"),
            file_reference=_optional_child_text(child, "FileReference"),
            method=_optional_child_text(child, "Method"),
            size=_optional_child_int(child, "EstimatedDataSize"),
            content_type=_optional_child_text(child, "ContentType"),
        )
        for child in attachments.children
        if isinstance(child, WbxmlElement) and child.tag == "Attachment"
    ]


def _require_tag(element: WbxmlElement, expected: str) -> None:
    if element.tag != expected:
        raise ValueError(f"Expected root tag {expected!r}, got {element.tag!r}")


def _require_success_status(element: WbxmlElement, *, response_name: str) -> None:
    status = _require_child_text(element, "Status")
    if status != "1":
        raise ValueError(f"{response_name} status {status!r} indicates failure")


def _require_child(element: WbxmlElement, tag: str) -> WbxmlElement:
    for child in element.children:
        if isinstance(child, WbxmlElement) and child.tag == tag:
            return child
    raise ValueError(f"Missing child tag {tag!r} under {element.tag!r}")


def _require_child_text(element: WbxmlElement, tag: str) -> str:
    value = _optional_child_text(element, tag)
    if value is None:
        raise ValueError(f"Missing text child tag {tag!r} under {element.tag!r}")
    return value


def _optional_child_text(element: WbxmlElement, tag: str) -> str | None:
    child = _find_child(element, tag)
    if child is None:
        return None

    for grandchild in child.children:
        if isinstance(grandchild, WbxmlText):
            return grandchild.text

    return None


def _optional_child_int(element: WbxmlElement, tag: str) -> int | None:
    value = _optional_child_text(element, tag)
    if value is None:
        return None
    return int(value)


def _find_child(element: WbxmlElement, tag: str) -> WbxmlElement | None:
    if element is None:
        return None
    for child in element.children:
        if isinstance(child, WbxmlElement) and child.tag == tag:
            return child
    return None
