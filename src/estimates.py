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
IRON_RE = re.compile(r"^(?P<num>[1-9])i$")
WOOD_RE = re.compile(r"^(?P<num>\d{1,2})W$")
HYBRID_RE = re.compile(r"^(?P<num>[1-7])H$")
UTIL_RE = re.compile(r"^(?P<num>[1-5])U$")

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

def estimate_club_speed(label: str, anchors: dict[str, Anchor]) -> Optional[float]:
    # Direct anchor
    if label in anchors:
        return anchors[label].club_speed_mph

    cat = category_of(label)

    # Hybrids: map 3H ~ Hybrid anchor; scale by hybrid number
    if HYBRID_RE.match(label):
        n = int(HYBRID_RE.match(label).group("num"))
        base = anchors.get("Hybrid")
        if not base:
            return None
        # Higher hybrid number => slightly slower
        return base.club_speed_mph - (n - 3) * 1.5

    # Utilities: between hybrid and long irons
    if UTIL_RE.match(label):
        n = int(UTIL_RE.match(label).group("num"))
        # 2U roughly between Hybrid (102) and 3i (100)
        h = anchors.get("Hybrid")
        i3 = anchors.get("3i")
        if not (h and i3):
            return None
        # 1U a touch faster than 2U, 5U slower
        base_2u = (h.club_speed_mph + i3.club_speed_mph) / 2
        return base_2u - (n - 2) * 1.2

    # Irons: interpolate/extrapolate from known 3i..9i anchors
    if IRON_RE.match(label):
        n = int(IRON_RE.match(label).group("num"))
        # We have 3..9
        known = {int(k[0]): anchors[k].club_speed_mph for k in anchors if re.match(r"^[3-9]i$", k)}
        if not known:
            return None
        # simple linear fit over iron number (works well enough for baseline speeds)
        xs = sorted(known.keys())
        # slope using endpoints
        slope = (known[xs[-1]] - known[xs[0]]) / (xs[-1] - xs[0])  # mph per iron number
        # y = y0 + slope*(n-x0)
        return known[xs[0]] + slope * (n - xs[0])

    # Woods: interpolate from 3W/5W anchors, plus driver
    if label == "Mini Driver":
        d = anchors.get("Driver")
        w3 = anchors.get("3W")
        if not (d and w3):
            return None
        return (d.club_speed_mph + w3.club_speed_mph) / 2

    if WOOD_RE.match(label):
        n = int(WOOD_RE.match(label).group("num"))
        d = anchors.get("Driver")
        w3 = anchors.get("3W")
        w5 = anchors.get("5W")
        if not (d and w3 and w5):
            return None
        # Use a gentle curve: as wood number increases, speed drops but flattens
        # Fit through 3W and 5W, then extend
        # Approx drop per +2 wood number from 3->5 is (110-106)=4 mph
        drop_per_wood = 2.0  # mph per wood number step (tunable, reasonable)
        # center around 3W
        return w3.club_speed_mph - (n - 3) * drop_per_wood

    if label == "Driver":
        return anchors.get("Driver").club_speed_mph if anchors.get("Driver") else None

    if cat == "wedge":
        # Wedge speed: anchor PW (46°) at 84 mph, drop ~1 mph per +2 loft
        pw = anchors.get("PW (46°)")
        loft = parse_loft(label)
        if not (pw and loft is not None):
            return None
        return pw.club_speed_mph - (loft - 46) * 0.5

    if cat == "putter":
        return None

    return None

def estimate_carry_from_speed(speed_mph: float, anchors: list[Anchor]) -> float:
    """
    Fit a smooth-ish power law carry ≈ a * speed^b using the TrackMan anchors.
    This captures non-linearity and avoids per-club hand tuning.
    """
    # Use anchors excluding putter
    pts = [(a.club_speed_mph, a.carry_yd) for a in anchors if a.category in ("wood", "hybrid", "iron", "wedge")]
    # Simple log-log linear regression
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
        # split irons by number
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
