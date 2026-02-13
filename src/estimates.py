import re
from dataclasses import dataclass
from typing import Optional, List, Tuple

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
HYBRID_RE= re.compile(r"^(?P<num>[1-7])H$")
UTIL_RE  = re.compile(r"^(?P<num>[1-5])U$")

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

# -------------------------
# Wedge loft interpolation helpers
# -------------------------
def _wedge_points(anchors: dict[str, Anchor]) -> List[Tuple[int, float, float]]:
    """
    Returns sorted list of (loft_deg, speed_mph, carry_yd) for wedge anchors.
    Uses Anchor.loft_deg if present; otherwise parses loft from label.
    """
    pts = []
    for a in anchors.values():
        if a.category != "wedge":
            continue
        loft = a.loft_deg if a.loft_deg is not None else parse_loft(a.label)
        if loft is None:
            continue
        pts.append((int(loft), float(a.club_speed_mph), float(a.carry_yd)))
    pts.sort(key=lambda x: x[0])
    return pts

def _interp_linear(x: float, x0: float, y0: float, x1: float, y1: float) -> float:
    if x1 == x0:
        return float(y0)
    t = (x - x0) / (x1 - x0)
    return float(y0 + t * (y1 - y0))

def _interp_by_loft(loft: int, pts: List[Tuple[int, float, float]], which: str) -> Optional[float]:
    """
    pts = [(loft, speed, carry), ...] sorted by loft
    which in {"speed","carry"}
    Linear interpolate within range; linear extrapolate outside range using nearest segment.
    """
    if len(pts) < 2:
        return None

    idx = 1 if which == "speed" else 2

    # exact match
    for L, s, c in pts:
        if L == loft:
            return float(s if which == "speed" else c)

    # below range -> extrapolate using first segment
    if loft < pts[0][0]:
        L0, s0, c0 = pts[0]
        L1, s1, c1 = pts[1]
        y0 = s0 if idx == 1 else c0
        y1 = s1 if idx == 1 else c1
        return _interp_linear(loft, L0, y0, L1, y1)

    # above range -> extrapolate using last segment
    if loft > pts[-1][0]:
        L0, s0, c0 = pts[-2]
        L1, s1, c1 = pts[-1]
        y0 = s0 if idx == 1 else c0
        y1 = s1 if idx == 1 else c1
        return _interp_linear(loft, L0, y0, L1, y1)

    # inside range -> interpolate between neighbors
    for i in range(1, len(pts)):
        L0, s0, c0 = pts[i - 1]
        L1, s1, c1 = pts[i]
        if L0 < loft < L1:
            y0 = s0 if idx == 1 else c0
            y1 = s1 if idx == 1 else c1
            return _interp_linear(loft, L0, y0, L1, y1)

    return None

# -------------------------
# Estimation
# -------------------------
def estimate_club_speed(label: str, anchors: dict[str, Anchor]) -> Optional[float]:
    # Direct anchor
    if label in anchors:
        return anchors[label].club_speed_mph

    cat = category_of(label)

    # Hybrids
    m = HYBRID_RE.match(label)
    if m:
        n = int(m.group("num"))
        base = anchors.get("Hybrid")
        if not base:
            return None
        return base.club_speed_mph - (n - 3) * 1.5

    # Utilities
    m = UTIL_RE.match(label)
    if m:
        n = int(m.group("num"))
        h = anchors.get("Hybrid")
        i3 = anchors.get("3i")
        if not (h and i3):
            return None
        base_2u = (h.club_speed_mph + i3.club_speed_mph) / 2
        return base_2u - (n - 2) * 1.2

    # Irons
    m = IRON_RE.match(label)
    if m:
        n = int(m.group("num"))
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
    m = WOOD_RE.match(label)
    if m:
        n = int(m.group("num"))
        w3 = anchors.get("3W")
        if not w3:
            return None
        drop_per_wood = 2.0
        return w3.club_speed_mph - (n - 3) * drop_per_wood

    if label == "Driver":
        return anchors.get("Driver").club_speed_mph if anchors.get("Driver") else None

    # ✅ Wedges: loft-based speed interpolation (more realistic than a fixed 0.5 mph/deg)
    if cat == "wedge":
        loft = parse_loft(label)
        if loft is None:
            return None
        pts = _wedge_points(anchors)
        spd = _interp_by_loft(loft, pts, which="speed")
        return None if spd is None else float(spd)

    return None

def estimate_carry_from_speed(speed_mph: float, anchors: list[Anchor]) -> float:
    """
    Global speed->carry power law (kept for non-wedge fallback).
    """
    pts = [(a.club_speed_mph, a.carry_yd) for a in anchors if a.category in ("wood", "hybrid", "iron", "wedge")]
    import math
    xs = [math.log(x) for x, _ in pts]
    ys = [math.log(y) for _, y in pts]
    n = len(xs)
    xbar = sum(xs) / n
    ybar = sum(ys) / n
    num = sum((xs[i]-xbar)*(ys[i]-ybar) for i in range(n))
    den = sum((xs[i]-xbar)**2 for i in range(n))
    b = num / den
    a = math.exp(ybar - b * xbar)
    return a * (speed_mph ** b)

def estimate_carry(label: str, speed_mph: float, anchors: dict[str, Anchor], anchors_list: list[Anchor]) -> float:
    """
    ✅ Wedges: loft-based carry interpolation.
    Everyone else: global speed->carry curve.
    """
    if category_of(label) == "wedge":
        loft = parse_loft(label)
        if loft is not None:
            pts = _wedge_points(anchors)
            c = _interp_by_loft(loft, pts, which="carry")
            if c is not None:
                return float(c)
    return float(estimate_carry_from_speed(speed_mph, anchors_list))

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
