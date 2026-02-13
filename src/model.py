import math
from dataclasses import dataclass
from typing import Optional

@dataclass
class ClubBaseline:
    label: str
    club_speed_mph: Optional[float]
    carry_yd: Optional[float]

def responsiveness_exponent(club_speed: float, driver_speed: float, p: float) -> float:
    r = club_speed / driver_speed
    return r ** p

def scaled_carry(carry0: float, chs_today: float, chs0: float, g: float) -> float:
    s = chs_today / chs0
    return carry0 * (s ** g)

def format_num(x: Optional[float]) -> str:
    return "—" if x is None else f"{x:.0f}"
