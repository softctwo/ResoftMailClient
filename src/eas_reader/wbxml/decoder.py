from eas_client.wbxml.codepages import CODE_PAGES
from eas_client.wbxml.models import (
    WbxmlDocument,
    WbxmlDecodeError,
    WbxmlElement,
    WbxmlHeader,
    WbxmlNode,
    WbxmlOpaque,
    WbxmlText,
)
from eas_client.wbxml.reader import ByteReader

SWITCH_PAGE_TOKEN = 0x00
END_TOKEN = 0x01
INLINE_STRING_TOKEN = 0x03
OPAQUE_TOKEN = 0xC3
TAG_CONTENT_FLAG = 0x40
TAG_ATTRIBUTES_FLAG = 0x80
TAG_MASK = 0x3F


def decode_header(data: bytes) -> WbxmlHeader:
    reader = ByteReader(data)
    try:
        return _read_header_from_reader(reader)
    except EOFError as exc:
        raise _wrap_eof_error(reader=reader, context="header") from exc


def decode_document(data: bytes) -> WbxmlDocument:
    reader = ByteReader(data)
    state = _DecoderState(reader=reader)
    try:
        header = _read_header_from_reader(reader)
    except EOFError as exc:
        raise _wrap_eof_error(reader=reader, context="header") from exc

    try:
        root = state.read_element()
        state.ensure_exhausted()
    except EOFError as exc:
        raise state.wrap_eof_error(context="body") from exc

    return WbxmlDocument(header=header, root=root)


def _read_header_from_reader(reader: ByteReader) -> WbxmlHeader:
    version = reader.read_byte()
    public_id = _read_mb_uint32(reader)
    charset = _read_mb_uint32(reader)
    string_table_length = _read_mb_uint32(reader)
    string_table = _read_bytes(reader, string_table_length)

    return WbxmlHeader(
        version=version,
        public_id=public_id,
        charset=charset,
        string_table=string_table,
    )


def _read_mb_uint32(reader: ByteReader) -> int:
    value = 0

    while True:
        octet = reader.read_byte()
        value = (value << 7) | (octet & 0x7F)
        if octet & 0x80 == 0:
            return value


def _read_bytes(reader: ByteReader, length: int) -> bytes:
    chunks = bytearray()
    for _ in range(length):
        chunks.append(reader.read_byte())
    return bytes(chunks)


def _read_inline_string(reader: ByteReader) -> str:
    buffer = bytearray()

    while True:
        octet = reader.read_byte()
        if octet == 0x00:
            return buffer.decode("utf-8")
        buffer.append(octet)


class _DecoderState:
    def __init__(self, reader: ByteReader) -> None:
        self.reader = reader
        self.current_page = 0

    def read_element(self) -> WbxmlElement:
        token = self._read_token()
        return self._read_element_with_token(token)

    def _read_children(self) -> list[WbxmlNode]:
        children: list[WbxmlNode] = []

        while True:
            token = self._read_token()
            if token == END_TOKEN:
                return children
            if token == INLINE_STRING_TOKEN:
                children.append(WbxmlText(text=_read_inline_string(self.reader)))
                continue
            if token == OPAQUE_TOKEN:
                children.append(WbxmlOpaque(opaque=self._read_opaque()))
                continue

            children.append(self._read_element_with_token(token))

    def _read_element_with_token(self, token: int) -> WbxmlElement:
        if token & TAG_ATTRIBUTES_FLAG:
            self._raise_decode_error(
                token=token,
                message="WBXML attributes are not supported",
            )

        tag_token = token & TAG_MASK
        page_tags = CODE_PAGES.get(self.current_page)
        if page_tags is None or tag_token not in page_tags:
            # 容错：跳过未知 token
            tag = f"_Unknown_page{self.current_page}_0x{tag_token:02X}"
        else:
            tag = page_tags[tag_token]
        has_content = bool(token & TAG_CONTENT_FLAG)
        children: list[WbxmlNode] = []

        if has_content:
            children = self._read_children()

        return WbxmlElement(tag=tag, children=children)

    def _read_token(self) -> int:
        token = self.reader.read_byte()

        while token == SWITCH_PAGE_TOKEN:
            self.current_page = self.reader.read_byte()
            token = self.reader.read_byte()

        return token

    def _read_opaque(self) -> bytes:
        length = _read_mb_uint32(self.reader)
        return _read_bytes(self.reader, length)

    def ensure_exhausted(self) -> None:
        try:
            token = self._read_token()
        except EOFError:
            return

        self._raise_decode_error(
            token=token,
            message="Trailing WBXML data after root element",
        )

    def _raise_decode_error(self, *, token: int, message: str) -> None:
        token_offset = self.reader.offset - 1
        raise WbxmlDecodeError(
            f"{message} at offset {token_offset} on page {self.current_page} "
            f"(token 0x{token:02X})"
        )

    def wrap_eof_error(self, *, context: str) -> WbxmlDecodeError:
        return _wrap_eof_error(
            reader=self.reader,
            context=context,
            current_page=self.current_page,
        )


def _wrap_eof_error(
    *,
    reader: ByteReader,
    context: str,
    current_page: int | None = None,
) -> WbxmlDecodeError:
    message = f"Unexpected end of WBXML stream while decoding {context} at offset {reader.offset}"
    if current_page is not None:
        message += f" on page {current_page}"
    return WbxmlDecodeError(message)
