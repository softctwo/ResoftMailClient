from __future__ import annotations

import base64
import xml.etree.ElementTree as ET

from eas_client.ews.models import (
    EwsAttachmentContent,
    EwsAttachmentSummary,
    EwsFindItemsResponse,
    EwsItemDetail,
    EwsItemSummary,
)

NS = {
    "soap": "http://schemas.xmlsoap.org/soap/envelope/",
    "m": "http://schemas.microsoft.com/exchange/services/2006/messages",
    "t": "http://schemas.microsoft.com/exchange/services/2006/types",
}


def parse_find_item_response(xml_text: str) -> EwsFindItemsResponse:
    root = _parse_xml(xml_text)
    _require_success(root, "FindItem")

    items: list[EwsItemSummary] = []
    for message in root.findall(".//t:Message", NS):
        item_id = message.find("t:ItemId", NS)
        if item_id is None or "Id" not in item_id.attrib:
            continue
        items.append(
            EwsItemSummary(
                item_id=item_id.attrib["Id"],
                change_key=item_id.attrib.get("ChangeKey"),
                subject=_find_text(message, "t:Subject"),
                sender=_mailbox_text(message.find("t:From/t:Mailbox", NS)),
                received_at=_find_text(message, "t:DateTimeReceived"),
                has_attachments=_find_text(message, "t:HasAttachments") == "true",
            )
        )

    return EwsFindItemsResponse(items=items)


def parse_get_item_response(xml_text: str) -> EwsItemDetail:
    root = _parse_xml(xml_text)
    _require_success(root, "GetItem")

    message = root.find(".//t:Message", NS)
    if message is None:
        raise ValueError("GetItem response did not contain a Message element")

    item_id = message.find("t:ItemId", NS)
    if item_id is None or "Id" not in item_id.attrib:
        raise ValueError("GetItem response did not contain an ItemId")

    attachments: list[EwsAttachmentSummary] = []
    for attachment in message.findall(".//t:FileAttachment", NS):
        attachment_id = attachment.find("t:AttachmentId", NS)
        if attachment_id is None or "Id" not in attachment_id.attrib:
            continue
        size = _find_text(attachment, "t:Size")
        attachments.append(
            EwsAttachmentSummary(
                attachment_id=attachment_id.attrib["Id"],
                name=_find_text(attachment, "t:Name"),
                content_type=_find_text(attachment, "t:ContentType"),
                size=int(size) if size else None,
                is_inline=_find_text(attachment, "t:IsInline") == "true",
            )
        )

    return EwsItemDetail(
        item_id=item_id.attrib["Id"],
        change_key=item_id.attrib.get("ChangeKey"),
        subject=_find_text(message, "t:Subject"),
        body=_find_text(message, "t:Body"),
        attachments=attachments,
    )


def parse_get_attachment_response(xml_text: str) -> EwsAttachmentContent:
    root = _parse_xml(xml_text)
    _require_success(root, "GetAttachment")

    attachment = root.find(".//t:FileAttachment", NS)
    if attachment is None:
        raise ValueError("GetAttachment response did not contain a FileAttachment element")

    attachment_id = attachment.find("t:AttachmentId", NS)
    if attachment_id is None or "Id" not in attachment_id.attrib:
        raise ValueError("GetAttachment response did not contain an AttachmentId")

    content = _find_text(attachment, "t:Content")
    if content is None:
        raise ValueError("GetAttachment response did not contain attachment content")

    return EwsAttachmentContent(
        attachment_id=attachment_id.attrib["Id"],
        name=_find_text(attachment, "t:Name"),
        content_type=_find_text(attachment, "t:ContentType"),
        content=base64.b64decode(content),
    )


def _parse_xml(xml_text: str) -> ET.Element:
    try:
        return ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise ValueError(f"Invalid EWS XML: {exc}") from exc


def _require_success(root: ET.Element, operation_name: str) -> None:
    response_message = root.find(".//m:ResponseMessages/*", NS)
    if response_message is None:
        raise ValueError(f"{operation_name} response did not contain ResponseMessages")

    response_class = response_message.attrib.get("ResponseClass")
    response_code = _find_text(response_message, "m:ResponseCode")
    if response_class != "Success" or response_code != "NoError":
        raise ValueError(
            f"{operation_name} failed: ResponseClass={response_class!r} ResponseCode={response_code!r}"
        )


def _find_text(element: ET.Element | None, path: str) -> str | None:
    if element is None:
        return None
    child = element.find(path, NS)
    if child is None:
        return None
    return child.text


def _mailbox_text(mailbox: ET.Element | None) -> str | None:
    if mailbox is None:
        return None
    name = _find_text(mailbox, "t:Name")
    address = _find_text(mailbox, "t:EmailAddress")
    if name and address:
        return f"{name} <{address}>"
    return name or address
