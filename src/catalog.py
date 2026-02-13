import re

WEDGE_RE = re.compile(r"^(PW|GW|SW|LW|Wedge)\s*\((\d{2})°\)$")
WOOD_RE = re.compile(r"^(\d{1,2})W$")
HYBRID_RE = re.compile(r"^(\d)H$")
UTIL_RE = re.compile(r"^(\d)U$")
IRON_RE = re.compile(r"^(\d)i$")

def _sort_key(label: str):
    # Rank groups in golf order
    # (group_rank, within_group_rank, tiebreaker)
    if label == "Driver":
        return (0, 0, label)
    if label == "Mini Driver":
        return (0, 1, label)

    m = WOOD_RE.match(label)
    if m:
        return (1, int(m.group(1)), label)

    m = HYBRID_RE.match(label)
    if m:
        return (2, int(m.group(1)), label)

    m = UTIL_RE.match(label)
    if m:
        return (3, int(m.group(1)), label)

    m = IRON_RE.match(label)
    if m:
        return (4, int(m.group(1)), label)

    m = WEDGE_RE.match(label)
    if m:
        loft = int(m.group(2))
        # named wedges still sort by loft
        return (5, loft, label)

    if label == "Putter":
        return (6, 0, label)

    # fallback
    return (9, 999, label)

def build_full_catalog() -> list[str]:
    clubs: list[str] = []

    # Woods
    clubs += ["Driver", "Mini Driver"]
    clubs += [f"{n}W" for n in [2, 3, 4, 5, 7, 9, 11]]

    # Hybrids
    clubs += [f"{n}H" for n in range(1, 8)]

    # Utilities
    clubs += [f"{n}U" for n in range(1, 6)]

    # Irons
    clubs += [f"{n}i" for n in range(1, 10)]

    # Named wedges you care about (and common alternates)
    clubs += ["PW (46°)", "GW (50°)", "SW (54°)", "SW (56°)", "LW (58°)", "LW (60°)"]

    # Full wedge loft coverage
    clubs += [f"Wedge ({d}°)" for d in range(40, 65)]

    # Putter
    clubs += ["Putter"]

    # De-dupe then sort with golf logic
    clubs = list(dict.fromkeys(clubs))
    clubs.sort(key=_sort_key)
    return clubs
