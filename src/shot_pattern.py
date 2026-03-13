from __future__ import annotations

import math
import random
from html import escape
from typing import Dict, List, Tuple

from src.estimates import category_of

Point = Tuple[float, float]  # (x_left_right_yd, y_carry_yd)


def _title_case_shape(shape: str) -> str:
    return (shape or "Straight").strip().title()


def _shape_bias(shape: str, carry: float, category: str) -> float:
    shape = (shape or "Straight").lower()

    # Draw = left bias (negative x), Fade = right bias (positive x)
    scale = {
        "wood": 0.020,
        "hybrid": 0.018,
        "utility": 0.017,
        "iron": 0.015,
        "wedge": 0.010,
    }.get(category, 0.015)

    if shape == "fade":
        return carry * scale
    if shape == "draw":
        return -carry * scale
    return 0.0


def _shape_angle_deg(shape: str, category: str) -> float:
    """
    Golf-intuitive rendered angle.
    Positive = fade feel (left-to-right)
    Negative = draw feel (right-to-left)
    """
    shape = (shape or "Straight").lower()

    base = {
        "wood": 22.0,
        "hybrid": 18.0,
        "utility": 16.0,
        "iron": 13.0,
        "wedge": 10.0,
    }.get(category, 12.0)

    if shape == "fade":
        return base
    if shape == "draw":
        return -base
    return 0.0


def pattern_defaults(label: str, carry: float) -> Dict[str, float | str]:
    category = category_of(label)

    cfg = {
        "wood":    {"lat_frac": 0.050, "dist_frac": 0.035, "min_lat": 8.0, "min_dist": 6.0},
        "hybrid":  {"lat_frac": 0.042, "dist_frac": 0.032, "min_lat": 6.0, "min_dist": 5.0},
        "utility": {"lat_frac": 0.040, "dist_frac": 0.030, "min_lat": 5.5, "min_dist": 4.5},
        "iron":    {"lat_frac": 0.036, "dist_frac": 0.028, "min_lat": 4.0, "min_dist": 3.5},
        "wedge":   {"lat_frac": 0.030, "dist_frac": 0.026, "min_lat": 2.5, "min_dist": 2.5},
    }.get(category, {"lat_frac": 0.038, "dist_frac": 0.030, "min_lat": 4.0, "min_dist": 4.0})

    lateral_std = max(cfg["min_lat"], carry * cfg["lat_frac"])
    distance_std = max(cfg["min_dist"], carry * cfg["dist_frac"])

    return {
        "category": category,
        "lateral_std": lateral_std,
        "distance_std": distance_std,
        "start_std": lateral_std * 0.58,
        "curve_std": lateral_std * 0.62,
    }


def simulate_shot_pattern(
    label: str,
    carry: float,
    total: float,
    shape: str = "Straight",
    n: int = 220,
    seed: int = 7,
) -> Dict[str, object]:
    defaults = pattern_defaults(label, carry)
    category = str(defaults["category"])
    rng = random.Random(seed)

    shape_bias = _shape_bias(shape, carry, category)
    rollout = max(0.0, total - carry)

    points: List[Point] = []
    totals: List[Point] = []

    start_std = float(defaults["start_std"])
    curve_std = float(defaults["curve_std"])
    distance_std = float(defaults["distance_std"])

    for _ in range(n):
        y = max(0.0, rng.gauss(carry, distance_std))
        start_x = rng.gauss(0.0, start_std)
        curve_x = rng.gauss(shape_bias, curve_std)
        x = start_x + curve_x

        rollout_noise = rng.gauss(0.0, max(0.3, rollout * 0.12))
        total_y = max(y, y + rollout + rollout_noise)
        total_x = x + rng.gauss(shape_bias * 0.10, max(0.2, abs(shape_bias) * 0.10 + rollout * 0.03))

        points.append((x, y))
        totals.append((total_x, total_y))

    return {
        "label": label,
        "shape": _title_case_shape(shape),
        "carry_center": carry,
        "total_center": total,
        "carry_points": points,
        "total_points": totals,
        "category": category,
    }


def _mean(values: List[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _quantile(values: List[float], q: float) -> float:
    if not values:
        return 0.0
    xs = sorted(values)
    if len(xs) == 1:
        return xs[0]
    idx = (len(xs) - 1) * q
    lo = int(math.floor(idx))
    hi = int(math.ceil(idx))
    if lo == hi:
        return xs[lo]
    frac = idx - lo
    return xs[lo] * (1 - frac) + xs[hi] * frac


def summarize_pattern(points: List[Point]) -> Dict[str, float | str]:
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]

    mean_x = _mean(xs)
    mean_y = _mean(ys)
    p10_x, p90_x = _quantile(xs, 0.10), _quantile(xs, 0.90)
    p10_y, p90_y = _quantile(ys, 0.10), _quantile(ys, 0.90)

    width_80 = p90_x - p10_x
    depth_80 = p90_y - p10_y

    if mean_x > 2.0:
        bias = "Right Bias"
    elif mean_x < -2.0:
        bias = "Left Bias"
    else:
        bias = "Centered"

    return {
        "mean_x": mean_x,
        "mean_y": mean_y,
        "width_80": width_80,
        "depth_80": depth_80,
        "bias_note": bias,
    }


def _rendered_ellipse_from_points(
    points: List[Point],
    shape: str,
    category: str,
    n_std_x: float,
    n_std_y: float,
) -> Tuple[float, float, float, float, float]:
    """
    Use actual simulated center/spread, but guide the rendered angle by shot shape.
    """
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]

    mx = _mean(xs)
    my = _mean(ys)

    p10_x, p90_x = _quantile(xs, 0.10), _quantile(xs, 0.90)
    p10_y, p90_y = _quantile(ys, 0.10), _quantile(ys, 0.90)

    width_80 = max(1.0, p90_x - p10_x)
    depth_80 = max(1.0, p90_y - p10_y)

    rx = max(1.0, (width_80 / 2.0) * n_std_x)
    ry = max(1.0, (depth_80 / 2.0) * n_std_y)

    angle = _shape_angle_deg(shape, category)

    return mx, my, rx, ry, angle


def render_shot_pattern_svg(label: str, shape: str, carry: float, total: float, pattern: Dict[str, object]) -> str:
    carry_points: List[Point] = pattern["carry_points"]  # type: ignore[index]
    total_points: List[Point] = pattern["total_points"]  # type: ignore[index]
    category = str(pattern.get("category", category_of(label)))
    shape_title = _title_case_shape(str(pattern.get("shape", shape)))
    stats = summarize_pattern(carry_points)

    all_x = [p[0] for p in carry_points + total_points]
    all_y = [p[1] for p in carry_points + total_points]

    # Tighter framing so the pattern fills the card better
    x_extent = max(10.0, max(abs(min(all_x)), abs(max(all_x))) * 1.32)
    y_min = max(0.0, min(all_y) - 10)
    y_max = max(total + 10, max(all_y) + 10)

    W, H = 900, 450
    ml, mr, mt, mb = 52, 30, 18, 34
    pw, ph = W - ml - mr, H - mt - mb

    def sx(x: float) -> float:
        return ml + ((x + x_extent) / (2 * x_extent)) * pw

    def sy(y: float) -> float:
        return H - mb - ((y - y_min) / (y_max - y_min)) * ph

    # Slightly larger zones so the visual reads faster
    outer = _rendered_ellipse_from_points(carry_points, shape_title, category, 1.30, 1.26)
    inner = _rendered_ellipse_from_points(carry_points, shape_title, category, 0.74, 0.72)

    def ellipse_svg(e: Tuple[float, float, float, float, float], fill: str, opacity: float) -> str:
        cx, cy, rx, ry, ang = e
        px = sx(cx)
        py = sy(cy)
        prx = abs(sx(rx) - sx(0))
        pry = abs(sy(cy + ry) - sy(cy))
        return (
            f'<ellipse cx="{px:.2f}" cy="{py:.2f}" rx="{prx:.2f}" ry="{pry:.2f}" '
            f'transform="rotate({-ang:.2f} {px:.2f} {py:.2f})" fill="{fill}" opacity="{opacity:.3f}" />'
        )

    dots = []
    for x, y in carry_points[:150]:
        dots.append(
            f'<circle cx="{sx(x):.2f}" cy="{sy(y):.2f}" r="2.2" fill="#0B8A61" opacity="0.10" />'
        )

    guide_levels = []
    if carry - 12 > y_min:
        guide_levels.append((carry - 12, ""))
    guide_levels.append((carry, f"Carry {carry:.0f}"))
    if total > carry + 1:
        guide_levels.append((total, f"Total {total:.0f}"))

    guides = []
    for gy, label_txt in guide_levels:
        guides.append(
            f'<line x1="{ml}" y1="{sy(gy):.2f}" x2="{W-mr}" y2="{sy(gy):.2f}" '
            f'stroke="#10201A" stroke-opacity="0.075" stroke-dasharray="5 8" />'
        )
        if label_txt:
            guides.append(
                f'<text x="{W-mr-2}" y="{sy(gy)-5:.2f}" text-anchor="end" fill="#10201A" fill-opacity="0.42" '
                f'font-size="12" font-weight="700">{escape(label_txt)}</text>'
            )

    target_x = sx(0)
    center_x = sx(float(stats["mean_x"]))
    center_y = sy(float(stats["mean_y"]))

    bias_note = escape(str(stats["bias_note"]))
    club_label = escape(label)

    return f"""
<div style="width:100%; background: rgba(255,255,255,0.62); border:1px solid rgba(16,32,26,0.08); border-radius:24px; padding:18px 18px 14px 18px; box-sizing:border-box;">
  <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:12px; flex-wrap:wrap; margin-bottom:10px;">
    <div>
      <div style="font-size:23px; line-height:1.12; font-weight:900; color:#10201A;">{club_label}</div>
      <div style="margin-top:4px; font-size:13px; line-height:1.2; color:rgba(16,32,26,0.58); font-weight:800;">{escape(shape_title)} Pattern</div>
    </div>
    <div style="padding:6px 12px; border-radius:999px; border:1px solid rgba(16,32,26,0.10); background:rgba(255,255,255,0.72); font-size:13px; font-weight:800; color:rgba(16,32,26,0.78);">
      Carry {carry:.0f} • Total {total:.0f}
    </div>
  </div>

  <svg viewBox="0 0 {W} {H}" width="100%" style="display:block; width:100%; border-radius:20px; background:rgba(255,255,255,0.38);" aria-label="{club_label} Shot Pattern">
    <defs>
      <linearGradient id="outerGlow" x1="0" x2="0" y1="0" y2="1">
        <stop offset="0%" stop-color="#10A874" stop-opacity="0.22" />
        <stop offset="100%" stop-color="#006747" stop-opacity="0.09" />
      </linearGradient>
      <linearGradient id="innerGlow" x1="0" x2="0" y1="0" y2="1">
        <stop offset="0%" stop-color="#0E9B6B" stop-opacity="0.38" />
        <stop offset="100%" stop-color="#006747" stop-opacity="0.16" />
      </linearGradient>
    </defs>

    <rect x="0" y="0" width="{W}" height="{H}" rx="22" fill="rgba(255,255,255,0.28)" />
    {''.join(guides)}

    <line x1="{target_x:.2f}" y1="{mt}" x2="{target_x:.2f}" y2="{H-mb}" stroke="#D4AF37" stroke-width="2.2" stroke-opacity="0.94" />
    <line x1="{center_x:.2f}" y1="{mt+12}" x2="{center_x:.2f}" y2="{H-mb}" stroke="#0B8A61" stroke-width="1.5" stroke-opacity="0.18" stroke-dasharray="6 7" />

    {ellipse_svg(outer, 'url(#outerGlow)', 1.0)}
    {ellipse_svg(inner, 'url(#innerGlow)', 1.0)}
    {''.join(dots)}

    <circle cx="{center_x:.2f}" cy="{center_y:.2f}" r="6.6" fill="#006747" fill-opacity="0.96" />
    <circle cx="{target_x:.2f}" cy="{sy(carry):.2f}" r="4.5" fill="#D4AF37" fill-opacity="0.96" />

    <text x="{target_x+9:.2f}" y="{mt+14:.2f}" fill="#10201A" fill-opacity="0.52" font-size="12" font-weight="700">Target Line</text>
    <text x="{center_x+9:.2f}" y="{center_y-10:.2f}" fill="#10201A" fill-opacity="0.52" font-size="12" font-weight="700">Mean Finish</text>
  </svg>

  <div style="display:grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap:10px; margin-top:12px;">
    <div style="border:1px solid rgba(16,32,26,0.08); border-radius:14px; padding:10px 10px; background:rgba(255,255,255,0.60);">
      <div style="font-size:12px; font-weight:800; color:rgba(16,32,26,0.58); margin-bottom:3px;">80% Width</div>
      <div style="font-size:20px; font-weight:900; color:#004C35;">{float(stats['width_80']):.0f} Yd</div>
    </div>
    <div style="border:1px solid rgba(16,32,26,0.08); border-radius:14px; padding:10px 10px; background:rgba(255,255,255,0.60);">
      <div style="font-size:12px; font-weight:800; color:rgba(16,32,26,0.58); margin-bottom:3px;">80% Depth</div>
      <div style="font-size:20px; font-weight:900; color:#004C35;">{float(stats['depth_80']):.0f} Yd</div>
    </div>
    <div style="border:1px solid rgba(16,32,26,0.08); border-radius:14px; padding:10px 10px; background:rgba(255,255,255,0.60);">
      <div style="font-size:12px; font-weight:800; color:rgba(16,32,26,0.58); margin-bottom:3px;">Bias</div>
      <div style="font-size:20px; font-weight:900; color:#004C35;">{bias_note}</div>
    </div>
  </div>
</div>
"""
