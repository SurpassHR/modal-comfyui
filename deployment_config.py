from __future__ import annotations


DEFAULT_GPU_FALLBACKS = ("L4", "A10G", "T4")


def _split_csv(value: str | None) -> list[str]:
    """Split a comma-separated environment value, dropping empty entries."""
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def parse_gpu_fallbacks(value: str | None) -> str | list[str]:
    """Parse MODAL_GPU as an ordered, comma-separated fallback list.

    Names are normalized to uppercase and duplicates are removed. A single
    value is returned as a string so the Modal decorator receives the same
    shape users have always used; multiple values are returned as a list.
    """
    items = [item.upper() for item in _split_csv(value)]
    items = _dedupe(items)
    if not items:
        items = list(DEFAULT_GPU_FALLBACKS)
    return items[0] if len(items) == 1 else items


def parse_regions(value: str | None) -> str | list[str] | None:
    """Parse MODAL_REGIONS as an ordered, comma-separated compute region list.

    An empty value means global scheduling (no region pinning). A single
    region is returned as a string; multiple regions are returned as a list.
    """
    items = [item.lower() for item in _split_csv(value)]
    items = _dedupe(items)
    if not items:
        return None
    return items[0] if len(items) == 1 else items
