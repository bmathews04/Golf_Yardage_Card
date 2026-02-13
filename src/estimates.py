import re
from dataclasses import dataclass
from typing import Optional

@dataclass
class Anchor:
    label: str
    club_speed_mph: float
    carry_yd: float
    category: str
    loft_deg: Optional[int] = None

WEDGE_RE = re.compile(r"^(?P<name>PW|GW|SW|LW|Wedge)\s*\((?P<loft>\d{2})°\)$")
IRON_RE  = re.compile(r"^(?P<num>[1-9])i$")
WOOD_RE  = re.compile(r"^(?P<num>\d{1,2})W$")
HYBRID_RE = re.compile(r"^(?P<num>[1-7])H$")
UTIL_RE   = re.compile(r"^(?P<num>[1-5])U$")

def parse_loft(label: str) -> Optional[int]:
    m = WEDGE_RE.match(label)
    return int(m.group("loft")) if m else None

def category_of(label: str) -> str:
    if label in ["Driver", "Mini Driver"] or WOOD_RE.match(label):
        return "wood"
    if HYBRID_RE.match(label):
        return "hybrid"
    if UTIL_RE.match(label):
        return "utility"
    if IRON_RE.match(label):
        return "iron"
    if WEDGE_RE.match(label) or label.startswith("Wedge"):
        return "wedge"
    if label == "Putter":
        return "putter"
    return "unknown"

def anchors_by_label(anchors: list[Anchor]) -> dict[str, Anchor]:
    return {a.label: a for a in anchors}

# ---------------------------
# NEW: wedge loft-based helpers (fit from your wedge anchors)
# ---------------------------
def _wedge_anchor_points(anchors: dict[str, Anchor]):
    pts = []
    for a in anchors.values():
        if a.category == "wedge":
            loft = a.loft_deg if a.loft_deg is not None else parse_loft(a.label)
            if loft is not None:
                pts.append((float(loft), float(a.club_speed_mph), float(a.carry_yd)))
    pts.sort(key=lambda x: x[0])
    return pts

def _fit_line(xs: list[float], ys: list[float]) -> tuple[float, float]:
    """
    Simple least squares fit: y = m*x + b
    Returns (m, b). Requires len(xs) >= 2
    """
    n = len(xs)
    xbar = sum(xs) / n
    ybar = sum(ys) / n
    num = sum((xs[i] - xbar) * (ys[i] - ybar) for i in range(n))
    den = sum((xs[i] - xbar) ** 2 for i in range(n))
    m = num / den if den != 0 else 0.0
    b = ybar - m * xbar
    return m, b

def estimate_wedge_speed_from_loft(loft: int, anchors: dict[str, Anchor]) -> Optional[float]:
    pts = _wedge_anchor_points(anchors)
    if len(pts) < 2:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    m, b = _fit_line(xs, ys)
    return m * float(loft) + b

def estimate_wedge_carry_from_loft(loft: int, anchors: dict[str, Anchor]) -> Optional[float]:
    """
    Prefer wedge carry based on loft interpolation/extrapolation from wedge anchors.
    """
    pts = _wedge_anchor_points(anchors)
    if len(pts) < 2:
        return None

    # exact loft present
    for L, _, C in pts:
        if int(round(L)) == int(loft):
            return float(C)

    # bracket & interpolate
    lofts = [p[0] for p in pts]
    carries = [p[2] for p in pts]

    # below range -> extrapolate using first two
    if loft <= lofts[0]:
        x0, x1 = lofts[0], lofts[1]
        y0, y1 = carries[0], carries[1]
        t = (float(loft) - x0) / (x1 - x0)
        return y0 + t * (y1 - y0)

    # above range -> extrapolate using last two
    if loft >= lofts[-1]:
        x0, x1 = lofts[-2], lofts[-1]
        y0, y1 = carries[-2], carries[-1]
        t = (float(loft) - x0) / (x1 - x0)
        return y0 + t * (y1 - y0)

    # inside range -> interpolate
    for i in range(len(lofts) - 1):
        if lofts[i] <= loft <= lofts[i + 1]:
            x0, x1 = lofts[i], lofts[i + 1]
            y0, y1 = carries[i], carries[i + 1]
            t = (float(loft) - x0) / (x1 - x0)
            return y0 + t * (y1 - y0)

    return None

# ---------------------------
# Your existing speed estimator (modified wedge section)
# ---------------------------
def estimate_club_speed(label: str, anchors: dict[str, Anchor]) -> Optional[float]:
    # Direct anchor
    if label in anchors:
        return anchors[label].club_speed_mph

    cat = category_of(label)

    # Hybrids
    if HYBRID_RE.match(label):
        n = int(HYBRID_RE.match(label).group("num"))
        base = anchors.get("Hybrid")
        if not base:
            return None
        return base.club_speed_mph - (n - 3) * 1.5

    # Utilities
    if UTIL_RE.match(label):
        n = int(UTIL_RE.match(label).group("num"))
        h = anchors.get("Hybrid")
        i3 = anchors.get("3i")
        if not (h and i3):
            return None
        base_2u = (h.club_speed_mph + i3.club_speed_mph) / 2
        return base_2u - (n - 2) * 1.2

    # Irons
    if IRON_RE.match(label):
        n = int(IRON_RE.match(label).group("num"))
        known = {int(k[0]): anchors[k].club_speed_mph for k in anchors if re.match(r"^[3-9]i$", k)}
        if not known:
            return None
        xs = sorted(known.keys())
        slope = (known[xs[-1]] - known[xs[0]]) / (xs[-1] - xs[0])
        return known[xs[0]] + slope * (n - xs[0])

    # Mini Driver
    if label == "Mini Driver":
        d = anchors.get("Driver")
        w3 = anchors.get("3W")
        if not (d and w3):
            return None
        return (d.club_speed_mph + w3.club_speed_mph) / 2

    # Woods
    if WOOD_RE.match(label):
        n = int(WOOD_RE.match(label).group("num"))
        w3 = anchors.get("3W")
        if not w3:
            return None
        drop_per_wood = 2.0
        return w3.club_speed_mph - (n - 3) * drop_per_wood

    if label == "Driver":
        return anchors.get("Driver").club_speed_mph if anchors.get("Driver") else None

    # ✅ WEDGES: fit loft -> speed from your wedge anchors (Option A)
    if cat == "wedge":
        loft = parse_loft(label)
        if loft is None:
            return None
        spd = estimate_wedge_speed_from_loft(loft, anchors)
        return float(spd) if spd is not None else None

    if cat == "putter":
        return None

    return None

# ---------------------------
# Carry estimation
# ---------------------------
def estimate_carry_from_speed(speed_mph: float, anchors: list[Anchor]) -> float:
    """
    Fit a smooth-ish power law carry ≈ a * speed^b using anchors.
    (Used mostly for clubs without direct carry anchors.)
    """
    pts = [(a.club_speed_mph, a.carry_yd) for a in anchors if a.category in ("wood", "hybrid", "iron", "wedge")]

    import math
    xs = [math.log(x) for x, _ in pts]
    ys = [math.log(y) for _, y in pts]
    n = len(xs)
    xbar = sum(xs) / n
    ybar = sum(ys) / n
    num = sum((xs[i] - xbar) * (ys[i] - ybar) for i in range(n))
    den = sum((xs[i] - xbar) ** 2 for i in range(n))
    b = num / den
    a = math.exp(ybar - b * xbar)
    return a * (speed_mph ** b)

def responsiveness_exponent(club_speed: float, driver_speed: float, p: float) -> float:
    r = club_speed / driver_speed
    return r ** p

def scaled_carry(carry0: float, chs_today: float, chs0: float, g: float) -> float:
    s = chs_today / chs0
    return carry0 * (s ** g)

def rollout_for(label: str, rollout_cfg: dict) -> float:
    cat = category_of(label)
    if label == "Driver":
        return float(rollout_cfg.get("Driver", 15))
    if cat == "wood":
        return float(rollout_cfg.get("Woods", 10))
    if cat == "hybrid":
        return float(rollout_cfg.get("Hybrid", 6))
    if cat == "utility":
        return float(rollout_cfg.get("Utility", 5))
    if cat == "iron":
        m = IRON_RE.match(label)
        if m:
            n = int(m.group("num"))
            if n <= 4:
                return float(rollout_cfg.get("LongIrons", 5))
            if n <= 7:
                return float(rollout_cfg.get("MidIrons", 4))
            return float(rollout_cfg.get("ShortIrons", 3))
        return float(rollout_cfg.get("MidIrons", 4))
    if cat == "wedge":
        return float(rollout_cfg.get("Wedges", 1))
    return 0.0
