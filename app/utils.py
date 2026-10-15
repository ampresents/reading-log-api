def clamp_page(limit: int, offset: int) -> tuple[int, int]:
    lo = 1
    hi = 100
    limit = max(lo, min(limit, hi))
    offset = max(0, offset)
    return limit, offset
