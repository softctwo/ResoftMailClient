import base64

from eas_reader.eas.models import (
    AttachmentFetchResult,
    AttachmentSummary,
    FolderSummary,
    FolderSyncResponse,
    MessageDetail,
    MessageSummary,
    ProvisionResponse,
    SyncResponse,
)
from eas_reader.wbxml import WbxmlElement, WbxmlOpaque, WbxmlText, decode_document


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


def parse_item_operations_attachment_response(payload: bytes) -> AttachmentFetchResult:
    root = decode_document(payload).root
    _require_tag(root, "ItemOperations")
    _require_success_status(root, response_name="ItemOperations")

    response = _require_child(root, "Response")
    fetch = _require_child(response, "Fetch")
    _require_success_status(fetch, response_name="ItemOperations Fetch")

    file_reference = _optional_child_text(fetch, "FileReference")
    properties = _require_child(fetch, "Properties")
    content_type = _optional_child_text(properties, "ContentType")
    data = _optional_child_bytes(properties, "Data")
    if data is None:
        data = _require_child_bytes(properties, "Data")

    return AttachmentFetchResult(
        file_reference=file_reference,
        content_type=content_type,
        data=_decode_attachment_data(data),
    )


def parse_item_operations_message_response(payload: bytes) -> MessageDetail:
    root = decode_document(payload).root
    _require_tag(root, "ItemOperations")
    _require_success_status(root, response_name="ItemOperations")

    response = _require_child(root, "Response")
    fetch = _require_child(response, "Fetch")
    _require_success_status(fetch, response_name="ItemOperations Fetch")

    properties = _require_child(fetch, "Properties")
    body = _find_child(properties, "Body")
    return MessageDetail(
        collection_id=_require_child_text(fetch, "CollectionId"),
        server_id=_require_child_text(fetch, "ServerId"),
        subject=_optional_child_text(properties, "Subject"),
        sender=_optional_child_text(properties, "From"),
        to=_optional_child_text(properties, "To"),
        received_at=_optional_child_text(properties, "DateReceived"),
        body=_optional_child_text(body, "Data") if body is not None else None,
        body_type=_optional_child_text(body, "Type") if body is not None else None,
        attachments=_parse_attachments(properties),
    )


def parse_provision_response(payload: bytes) -> ProvisionResponse:
    root = decode_document(payload).root
    _require_tag(root, "Provision")

    status = _require_child_text(root, "Status")
    policies = _find_child(root, "Policies")
    policy = _find_child(policies, "Policy") if policies is not None else None
    policy_type = _optional_child_text(policy, "PolicyType") if policy is not None else None
    policy_key = _optional_child_text(policy, "PolicyKey") if policy is not None else None

    settings: dict[str, str] = {}
    data = _find_child(policy, "Data") if policy is not None else None
    if data is not None:
        settings.update(_collect_text_values(data))

    return ProvisionResponse(
        status=status,
        policy_type=policy_type,
        policy_key=policy_key,
        settings=settings,
    )


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


def _require_child_bytes(element: WbxmlElement, tag: str) -> bytes:
    value = _optional_child_bytes(element, tag)
    if value is None:
        raise ValueError(f"Missing binary child tag {tag!r} under {element.tag!r}")
    return value


def _optional_child_text(element: WbxmlElement, tag: str) -> str | None:
    child = _find_child(element, tag)
    if child is None:
        return None

    for grandchild in child.children:
        if isinstance(grandchild, WbxmlText):
            return grandchild.text

    return None


def _optional_child_bytes(element: WbxmlElement, tag: str) -> bytes | None:
    child = _find_child(element, tag)
    if child is None:
        return None

    for grandchild in child.children:
        if isinstance(grandchild, WbxmlText):
            return grandchild.text.encode("utf-8")
        if isinstance(grandchild, WbxmlOpaque):
            return grandchild.opaque

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


def _collect_text_values(element: WbxmlElement) -> dict[str, str]:
    values: dict[str, str] = {}
    for child in element.children:
        if not isinstance(child, WbxmlElement):
            continue

        text = _optional_text(child)
        if text is not None:
            values[child.tag] = text

        values.update(_collect_text_values(child))
    return values


def _optional_text(element: WbxmlElement) -> str | None:
    for child in element.children:
        if isinstance(child, WbxmlText):
            return child.text
    return None


def _decode_attachment_data(data: bytes) -> bytes:
    try:
        return base64.b64decode(data, validate=True)
    except Exception:
        return data


def parse_ping_response(data: bytes) -> dict:
    """Parse a Ping response. Returns dict with status and changed folders."""
    doc = decode_document(data)
    result = {"status": None, "folders": []}

    def _walk(node):
        tag = getattr(node, 'tag', '')
        text = getattr(node, 'text', None)

        if tag == 'Status':
            result['status'] = text
        elif tag == 'Folder':
            folder_info = {}
            for child in getattr(node, 'children', []):
                child_tag = getattr(child, 'tag', '')
                child_text = getattr(child, 'text', None)
                if child_tag == 'Id':
                    folder_info['id'] = child_text
                elif child_tag == 'Class':
                    folder_info['class'] = child_text
            if folder_info:
                result['folders'].append(folder_info)

        for child in getattr(node, 'children', []):
            _walk(child)

    _walk(doc.root)
    return result
