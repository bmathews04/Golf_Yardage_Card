from __future__ import annotations

import math
import random
from html import escape
from typing import Dict, List, Tuple

from src.estimates import category_of


Point = Tuple[float, float]  # (x_left_right_yd, y_carry_yd)


def _shape_bias(shape: str, carry: float, category: str) -> float:
    shape = (shape or "Straight").lower()
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


def pattern_defaults(label: str, carry: float) -> Dict[str, float]:
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
    category = defaults["category"]
    rng = random.Random(seed)

    shape_bias = _shape_bias(shape, carry, category)
    rollout = max(0.0, total - carry)

    points: List[Point] = []
    totals: List[Point] = []

    for _ in range(n):
        y = max(0.0, rng.gauss(carry, defaults["distance_std"]))
        start_x = rng.gauss(0.0, defaults["start_std"])
        curve_x = rng.gauss(shape_bias, defaults["curve_std"])
        x = start_x + curve_x

        rollout_noise = rng.gauss(0.0, max(0.3, rollout * 0.12))
        total_y = max(y, y + rollout + rollout_noise)
        total_x = x + rng.gauss(shape_bias * 0.10, max(0.2, abs(shape_bias) * 0.10 + rollout * 0.03))

        points.append((x, y))
        totals.append((total_x, total_y))

    return {
        "label": label,
        "shape": shape,
        "carry_center": carry,
        "total_center": total,
        "carry_points": points,
        "total_points": totals,
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
        miss = "Slight right bias"
    elif mean_x < -2.0:
        miss = "Slight left bias"
    else:
        miss = "Centered pattern"

    return {
        "mean_x": mean_x,
        "mean_y": mean_y,
        "width_80": width_80,
        "depth_80": depth_80,
        "miss_note": miss,
    }


def _covariance(points: List[Point]) -> Tuple[float, float, float, float, float]:
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    mx = _mean(xs)
    my = _mean(ys)
    n = max(1, len(points) - 1)
    var_x = sum((x - mx) ** 2 for x in xs) / n
    var_y = sum((y - my) ** 2 for y in ys) / n
    cov_xy = sum((x - mx) * (y - my) for x, y in points) / n
    return mx, my, var_x, var_y, cov_xy


def _ellipse_from_points(points: List[Point], n_std: float) -> Tuple[float, float, float, float, float]:
    mx, my, var_x, var_y, cov_xy = _covariance(points)

    term = math.sqrt(max(0.0, ((var_x - var_y) / 2.0) ** 2 + cov_xy ** 2))
    lam1 = max(1e-6, (var_x + var_y) / 2.0 + term)
    lam2 = max(1e-6, (var_x + var_y) / 2.0 - term)
    angle = 0.5 * math.atan2(2.0 * cov_xy, var_x - var_y)

    rx = n_std * math.sqrt(lam1)
    ry = n_std * math.sqrt(lam2)
    return mx, my, rx, ry, math.degrees(angle)


def render_shot_pattern_svg(label: str, shape: str, carry: float, total: float, pattern: Dict[str, object]) -> str:
    carry_points: List[Point] = pattern["carry_points"]  # type: ignore[index]
    total_points: List[Point] = pattern["total_points"]  # type: ignore[index]
    stats = summarize_pattern(carry_points)

    all_x = [p[0] for p in carry_points + total_points]
    all_y = [p[1] for p in carry_points + total_points]

    x_extent = max(12.0, max(abs(min(all_x)), abs(max(all_x))) * 1.35)
    y_min = max(0.0, min(all_y) - 14)
    y_max = max(total + 12, max(all_y) + 12)

    W, H = 760, 420
    ml, mr, mt, mb = 50, 28, 26, 48
    pw, ph = W - ml - mr, H - mt - mb

    def sx(x: float) -> float:
        return ml + ((x + x_extent) / (2 * x_extent)) * pw

    def sy(y: float) -> float:
        return H - mb - ((y - y_min) / (y_max - y_min)) * ph

    outer = _ellipse_from_points(carry_points, 1.65)
    inner = _ellipse_from_points(carry_points, 0.95)

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
    for x, y in carry_points[:140]:
        dots.append(
            f'<circle cx="{sx(x):.2f}" cy="{sy(y):.2f}" r="2.4" fill="#006747" opacity="0.12" />'
        )

    guide_levels = [carry - 15, carry, total]
    guides = []
    for idx, gy in enumerate(guide_levels):
        if gy < y_min or gy > y_max:
            continue
        label_txt = "Carry" if idx == 1 else ("Total" if idx == 2 else "")
        guides.append(
            f'<line x1="{ml}" y1="{sy(gy):.2f}" x2="{W-mr}" y2="{sy(gy):.2f}" '
            f'stroke="#10201a" stroke-opacity="0.10" stroke-dasharray="5 7" />'
        )
        if label_txt:
            guides.append(
                f'<text x="{W-mr-2}" y="{sy(gy)-6:.2f}" text-anchor="end" fill="#10201a" fill-opacity="0.55" '
                f'font-size="12" font-weight="700">{label_txt} {gy:.0f}</text>'
            )

    target_x = sx(0)
    center_x = sx(float(stats["mean_x"]))
    center_y = sy(float(stats["mean_y"]))

    shape_label = escape(shape)
    club_label = escape(label)
    miss_note = escape(str(stats["miss_note"]))

    return f"""
<div class="pattern-shell">
  <div class="pattern-meta">
    <div>
      <div class="pattern-title">{club_label} Shot Pattern</div>
      <div class="pattern-sub">{shape_label} • Monte Carlo visual using the app's modeled yardage</div>
    </div>
    <div class="pattern-chip">Carry {carry:.0f} • Total {total:.0f}</div>
  </div>

  <svg viewBox="0 0 {W} {H}" width="100%" class="pattern-svg" aria-label="{club_label} shot pattern">
    <defs>
      <linearGradient id="carryGlow" x1="0" x2="0" y1="0" y2="1">
        <stop offset="0%" stop-color="#0d8a61" stop-opacity="0.28" />
        <stop offset="100%" stop-color="#006747" stop-opacity="0.08" />
      </linearGradient>
      <linearGradient id="carryInner" x1="0" x2="0" y1="0" y2="1">
        <stop offset="0%" stop-color="#0d8a61" stop-opacity="0.42" />
        <stop offset="100%" stop-color="#006747" stop-opacity="0.18" />
      </linearGradient>
    </defs>

    <rect x="0" y="0" width="{W}" height="{H}" rx="24" fill="rgba(255,255,255,0.35)" />
    {''.join(guides)}
    <line x1="{target_x:.2f}" y1="{mt}" x2="{target_x:.2f}" y2="{H-mb}" stroke="#d4af37" stroke-width="2.2" stroke-opacity="0.95" />
    <line x1="{center_x:.2f}" y1="{mt+24}" x2="{center_x:.2f}" y2="{H-mb}" stroke="#006747" stroke-width="1.8" stroke-opacity="0.28" stroke-dasharray="6 7" />

    {ellipse_svg(outer, 'url(#carryGlow)', 1.0)}
    {ellipse_svg(inner, 'url(#carryInner)', 1.0)}
    {''.join(dots)}

    <circle cx="{center_x:.2f}" cy="{center_y:.2f}" r="6.5" fill="#006747" fill-opacity="0.95" />
    <circle cx="{target_x:.2f}" cy="{sy(carry):.2f}" r="4.2" fill="#d4af37" fill-opacity="0.95" />

    <text x="{target_x+8:.2f}" y="{mt+16}" fill="#10201a" fill-opacity="0.72" font-size="12" font-weight="800">Target line</text>
    <text x="{center_x+10:.2f}" y="{center_y-10:.2f}" fill="#10201a" fill-opacity="0.72" font-size="12" font-weight="800">Mean finish</text>
  </svg>

  <div class="pattern-stats">
    <div class="pattern-stat"><span>80% width</span><strong>{float(stats['width_80']):.0f} yd</strong></div>
    <div class="pattern-stat"><span>80% depth</span><strong>{float(stats['depth_80']):.0f} yd</strong></div>
    <div class="pattern-stat"><span>Tendency</span><strong>{miss_note}</strong></div>
  </div>
</div>
"""
