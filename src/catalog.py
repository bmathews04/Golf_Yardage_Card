def wedge_label(name: str, loft: int) -> str:
    return f"{name} ({loft}°)"

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

    # Named wedges with common loft defaults (still selectable even if player differs)
    clubs += [
        wedge_label("PW", 46),
        wedge_label("GW", 50),
        wedge_label("SW", 54),
        wedge_label("SW", 56),
        wedge_label("LW", 58),
        wedge_label("LW", 60),
    ]

    # Full wedge loft coverage as named generic wedges too (tournament bags vary)
    clubs += [f"Wedge ({d}°)" for d in range(40, 65)]

    # Putter
    clubs += ["Putter"]

    # De-dupe preserving order
    seen = set()
    ordered = []
    for c in clubs:
        if c not in seen:
            ordered.append(c)
            seen.add(c)
    return ordered
