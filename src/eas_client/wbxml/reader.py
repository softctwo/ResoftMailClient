class ByteReader:
    def __init__(self, data: bytes) -> None:
        self._data = data
        self._offset = 0

    @property
    def offset(self) -> int:
        return self._offset

    def read_byte(self) -> int:
        if self._offset >= len(self._data):
            raise EOFError(f"Unexpected end of WBXML stream at offset {self._offset}")

        value = self._data[self._offset]
        self._offset += 1
        return value
