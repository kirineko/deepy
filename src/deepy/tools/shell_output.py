from __future__ import annotations


def decode_shell_output(data: bytes, *, marker: str | None = None) -> tuple[str, str]:
    if not data:
        return "", "empty"
    if marker:
        marker_bytes = marker.encode("ascii")
        marker_index = data.find(marker_bytes)
        if marker_index >= 0:
            sentinel_start = marker_index
            if sentinel_start > 0 and data[sentinel_start - 1 : sentinel_start] == b"\n":
                sentinel_start -= 1
                if sentinel_start > 0 and data[sentinel_start - 1 : sentinel_start] == b"\r":
                    sentinel_start -= 1
            visible, visible_encoding = decode_shell_output_bytes(data[:sentinel_start])
            sentinel = data[sentinel_start:].decode("utf-8", errors="replace")
            return visible + sentinel, visible_encoding
    return decode_shell_output_bytes(data)


def decode_shell_output_bytes(data: bytes) -> tuple[str, str]:
    if not data:
        return "", "empty"
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16", errors="replace"), "utf-16"
    if _looks_like_utf16le(data):
        return data.decode("utf-16le", errors="replace"), "utf-16le"
    try:
        return data.decode("utf-8-sig"), "utf-8-sig" if data.startswith(b"\xef\xbb\xbf") else "utf-8"
    except UnicodeDecodeError:
        pass
    try:
        return data.decode("gb18030"), "gb18030"
    except UnicodeDecodeError:
        return data.decode("utf-8", errors="replace"), "utf-8-replace"


def _looks_like_utf16le(data: bytes) -> bool:
    if len(data) < 4:
        return False
    sample = data[: min(len(data), 4096)]
    odd_nuls = sample[1::2].count(0)
    even_nuls = sample[0::2].count(0)
    return odd_nuls >= max(2, len(sample) // 8) and odd_nuls > even_nuls * 2
