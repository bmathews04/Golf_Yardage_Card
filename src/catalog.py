def build_full_catalog(wedge_lofts=(40, 64)) -> list[str]:
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

    # Named wedges (name + loft handled in config for user’s set)
    clubs += ["PW", "GW", "SW", "LW"]

    # Loft wedges (full coverage)
    clubs += [f"Wedge ({d}°)" for d in range(wedge_lofts[0], wedge_lofts[1] + 1)]

    # Putter (optional completeness)
    clubs += ["Putter"]

    # De-dupe while preserving order
    seen = set()
    ordered = []
    for c in clubs:
        if c not in seen:
            ordered.append(c)
            seen.add(c)
    return ordered
