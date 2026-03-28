from dataclasses import dataclass, field


class WbxmlDecodeError(ValueError):
    pass


@dataclass(frozen=True)
class WbxmlHeader:
    version: int
    public_id: int
    charset: int
    string_table: bytes


@dataclass(frozen=True)
class WbxmlText:
    text: str


@dataclass(frozen=True)
class WbxmlOpaque:
    opaque: bytes


@dataclass(frozen=True)
class WbxmlElement:
    tag: str
    children: list["WbxmlNode"] = field(default_factory=list)


WbxmlNode = WbxmlElement | WbxmlOpaque | WbxmlText


@dataclass(frozen=True)
class WbxmlDocument:
    header: WbxmlHeader
    root: WbxmlElement
