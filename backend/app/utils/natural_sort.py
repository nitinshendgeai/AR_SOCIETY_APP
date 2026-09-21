import re

_CHUNK_RE = re.compile(r"\d+|\D+")


def natural_sort_key(value: str) -> str:
    """Key for ordering free-text codes like flat/unit numbers ("A-101",
    "1101", "A-1702") the way a person would, not the way plain string
    comparison does. Plain string order puts "A-1702" before "A-201"
    (because "1" < "2"); this zero-pads each digit run so the comparison
    stays numeric within otherwise-identical prefixes, while remaining a
    single string — so it's safe to mix formats (with/without a wing
    prefix) in one sort without a str/int comparison error.
    """
    return "".join(
        chunk.zfill(10) if chunk.isdigit() else chunk.lower()
        for chunk in _CHUNK_RE.findall(value or "")
    )
