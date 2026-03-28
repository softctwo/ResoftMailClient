from dataclasses import dataclass, field

from eas_reader.wbxml.codepages import CODE_PAGES

WBXML_HEADER = bytes([0x03, 0x01, 0x6A, 0x00])
SWITCH_PAGE_TOKEN = 0x00
END_TOKEN = 0x01
INLINE_STRING_TOKEN = 0x03
TAG_CONTENT_FLAG = 0x40


@dataclass(frozen=True)
class WbxmlRequestElement:
    page: int
    tag: str
    text: str | None = None
    children: list["WbxmlRequestElement"] = field(default_factory=list)


def encode_document(root: WbxmlRequestElement) -> bytes:
    buffer = bytearray(WBXML_HEADER)
    state = _EncoderState()
    buffer.extend(state.encode_element(root))
    return bytes(buffer)


class _EncoderState:
    def __init__(self) -> None:
        self.current_page = 0

    def encode_element(self, element: WbxmlRequestElement) -> bytes:
        buffer = bytearray()
        self._switch_page_if_needed(buffer, element.page)

        token = _lookup_token(element.page, element.tag)
        has_content = bool(element.children or element.text is not None)
        if has_content:
            token |= TAG_CONTENT_FLAG

        buffer.append(token)

        if element.text is not None:
            buffer.append(INLINE_STRING_TOKEN)
            buffer.extend(element.text.encode("utf-8"))
            buffer.append(0x00)

        for child in element.children:
            buffer.extend(self.encode_element(child))

        if has_content:
            buffer.append(END_TOKEN)

        return bytes(buffer)

    def _switch_page_if_needed(self, buffer: bytearray, target_page: int) -> None:
        if target_page == self.current_page:
            return

        buffer.extend((SWITCH_PAGE_TOKEN, target_page))
        self.current_page = target_page


def _lookup_token(page: int, tag: str) -> int:
    page_tags = CODE_PAGES.get(page)
    if page_tags is None:
        raise ValueError(f"Unknown WBXML code page {page} for tag {tag!r}")

    for token, known_tag in page_tags.items():
        if known_tag == tag:
            return token

    raise ValueError(f"Unknown WBXML tag {tag!r} on page {page}")
