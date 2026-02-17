from pathlib import Path
import streamlit as st
import yaml

from src.catalog import build_full_catalog
from src.estimates import (
    Anchor, anchors_by_label,
    estimate_club_speed, estimate_carry_from_speed,
    responsiveness_exponent, scaled_carry, rollout_for, category_of
)

from src.estimates import (
    Anchor, anchors_by_label,
    estimate_club_speed, estimate_carry, estimate_carry_from_speed,
    responsiveness_exponent, scaled_carry, rollout_for, category_of
)

# ---------------------------
# Page config (MUST be first Streamlit call)
# ---------------------------
st.set_page_config(page_title="Yardage Card", layout="wide")

# ---------------------------
# Top whitespace kill + hide Streamlit chrome
# ---------------------------
st.markdown("""
<style>
/* --- Kill Streamlit chrome + reserved space (mobile Safari friendly) --- */
header[data-testid="stHeader"] { display: none !important; }
div[data-testid="stToolbar"] { display: none !important; }
div[data-testid="stDecoration"] { display: none !important; }
#MainMenu { display: none !important; }
footer { display: none !important; }

/* Make the app start at the very top */
div[data-testid="stAppViewContainer"] > section.main { padding-top: 0rem !important; }
div[data-testid="stAppViewContainer"] > section.main > div.block-container {
  padding-top: 0rem !important;
  margin-top: 0rem !important;
}

/* If iOS still shows a sliver, pull everything up slightly */
@media (max-width: 768px){
  div[data-testid="stAppViewContainer"] > section.main > div.block-container {
    margin-top: -10px !important;
  }
}

/* Tighten title spacing */
h1 { margin-top: 0.0rem !important; margin-bottom: 0.15rem !important; }
[data-testid="stCaptionContainer"] { margin-top: 0.0rem !important; margin-bottom: 0.5rem !important; }
</style>
""", unsafe_allow_html=True)

# ---------------------------
# Augusta / Masters-inspired theme (CSS) + Pro visuals (badges, bars, gaps)
# ---------------------------
st.markdown("""
<style>
/* Augusta-inspired palette */
:root{
  --augusta-green: #006747;
  --augusta-green-dark: #004c35;
  --azalea-pink: #e86aa3;
  --gold: #d4af37;
  --cream: #fbf7ef;
  --ink: #10201a;
  --muted: rgba(16,32,26,0.65);
  --line: rgba(16,32,26,0.12);
}

/* background */
.stApp {
  background: linear-gradient(180deg, var(--cream) 0%, #ffffff 65%);
}

/* container */
.block-container {
  padding-top: 0.15rem !important;
  padding-bottom: 2.5rem;
  max-width: 900px;
}
h1 { margin-bottom: 0.2rem; color: var(--ink); }
[data-testid="stCaptionContainer"] { margin-bottom: 0.6rem; color: var(--muted); }

/* mobile padding */
@media (max-width: 768px){
  .block-container { padding-left: 0.75rem; padding-right: 0.75rem; }
}

/* expander */
details summary { font-size: 0.95rem; color: var(--augusta-green); }

/* input labels */
label, .stMarkdown { color: var(--ink); }

/* divider */
hr { border-color: var(--line) !important; }

/* section headers */
.section-title{ display:flex; align-items:center; gap:10px; }
.section-dot{
  width: 6px;
  height: 18px;
  border-radius: 999px;
  background: var(--azalea-pink);
  box-shadow: none;
}

/* a subtle gold underline on headers */
.section-underline{
  height: 2px;
  width: 52px;
  border-radius: 999px;
  background: linear-gradient(90deg, var(--gold), rgba(212,175,55,0.15));
  margin: 6px 0 10px 20px;
}

/* badges */
.badges { display:flex; gap:8px; flex-wrap:wrap; margin: 6px 0 12px 0; }
.badge {
  padding: 4px 10px;
  border-radius: 999px;
  border: 1px solid rgba(16,32,26,0.10);
  background: rgba(255,255,255,0.70);
  font-size: 0.78rem;
  font-weight: 800;
  color: rgba(16,32,26,0.75);
  max-width: 100%;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  box-shadow: 0 1px 0 rgba(0,0,0,0.03);
}

/* cards */
.ycard {
  padding: 10px 12px;
  border: 1px solid var(--line);
  border-left: 6px solid var(--augusta-green);
  background: rgba(255,255,255,0.75);
  backdrop-filter: blur(4px);
  border-radius: 16px;
  margin-bottom: 10px;
  box-shadow: 0 1px 0 rgba(0,0,0,0.03);
  position: relative;
  overflow: hidden;
  transition: transform 120ms ease, box-shadow 120ms ease, border-color 120ms ease;
}
.ycard:hover{
  transform: translateY(-1px);
  box-shadow: 0 6px 18px rgba(0,0,0,0.06);
  border-color: rgba(16,32,26,0.18);
}
/* subtle “sheen” highlight */
.ycard:before{
  content:"";
  position:absolute;
  left:0; top:0;
  width:100%; height:40%;
  background: linear-gradient(180deg, rgba(255,255,255,0.55), rgba(255,255,255,0.0));
  pointer-events:none;
}

.yrow { display:flex; justify-content: space-between; align-items: baseline; gap: 10px; }
.yclub { font-size: 1.0rem; font-weight: 800; color: var(--ink); }
.ycloft{
  font-size: 0.78rem;
  font-weight: 700;
  color: rgba(16,32,26,0.50);
  margin-left: 6px;
}
.yvals {
  font-size: 1.18rem;
  font-weight: 900;
  color: var(--augusta-green-dark);
  letter-spacing: -0.02em;
  text-shadow: 0 1px 0 rgba(255,255,255,0.6);
}
.ysub  { opacity: 0.75; font-size: 0.80rem; margin-top: 2px; color: var(--muted); }

/* carry bar */
.barwrap {
  width: 100%;
  height: 8px;
  background: rgba(16,32,26,0.08);
  border-radius: 999px;
  overflow: hidden;
  margin-top: 8px;
}
.barfill {
  height: 100%;
  background: linear-gradient(90deg, var(--augusta-green), var(--augusta-green-dark));
  border-radius: 999px;
  filter: saturate(1.05);
}

/* gap pill (reserve height so last card stays same size) */
.gapline{
  margin-top: 6px;
  display: flex;
  justify-content: flex-start;
  align-items: center;
  min-height: 24px;
}
.gappill{
  display:inline-block;
  padding: 3px 8px;
  border-radius: 999px;
  border: 1px solid rgba(16,32,26,0.08);
  background: rgba(255,255,255,0.65);
  font-size: 0.72rem;
  font-weight: 800;
  color: rgba(16,32,26,0.68);
  min-height: 18px;
}

/* wedges: mini grid */
.wgrid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 8px;
  margin-top: 8px;
}
.wcell {
  border: 1px solid rgba(16,32,26,0.10);
  border-radius: 12px;
  padding: 8px 8px;
  background: rgba(255,255,255,0.60);
  text-align: center;
}
.wlab {
  font-size: 0.72rem;
  font-weight: 800;
  color: rgba(16,32,26,0.70);
  letter-spacing: 0.02em;
}
.wval {
  margin-top: 2px;
  font-size: 1.05rem;
  font-weight: 900;
  color: var(--augusta-green-dark);
}
.wbarwrap{
  width: 100%;
  height: 6px;
  background: rgba(16,32,26,0.08);
  border-radius: 999px;
  overflow: hidden;
  margin-top: 6px;
}
.wbarfill{
  height: 100%;
  background: linear-gradient(90deg, var(--augusta-green), var(--augusta-green-dark));
  border-radius: 999px;
}

/* --- Tabs: classy pill treatment + clear active state --- */
div[data-testid="stTabs"] button{
  border-radius: 999px !important;
  padding: 6px 12px !important;
  transition: background-color 120ms ease, transform 120ms ease;
}
div[data-testid="stTabs"] button:hover{
  background: rgba(0,103,71,0.06) !important;
}
div[data-testid="stTabs"] button[aria-selected="true"]{
  background: rgba(0,103,71,0.08) !important;
  color: #004c35 !important;
  border-bottom: 3px solid #d4af37 !important;  /* gold underline */
}
div[data-testid="stTabs"] button[aria-selected="false"]{
  opacity: 1 !important; /* prevent “faded out” look */
}

/* Sticky ONLY on larger screens (mobile Safari can break scroll with big tables) */
@media (min-width: 900px){
  div[data-testid="stTabs"]{
    position: sticky;
    top: 0;
    z-index: 50;
    background: rgba(251,247,239,0.95);
    backdrop-filter: blur(6px);
    padding-top: 4px;
  }
}

.ycard.wedge { padding: 10px 12px; }
</style>
""", unsafe_allow_html=True)

# Wedge grid sizing helper (if you're using the 4-wide version)
st.markdown("""
<style>
/* 4-wide wedge grid (Choke, 75, 50, 25) */
.wgrid.wgrid4{
  grid-template-columns: repeat(4, 1fr) !important;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<style>
/* Tabs: clean Augusta (no filled pill) */
div[data-testid="stTabs"] button{
  border-radius: 10px !important;
  padding: 6px 10px !important;
  background: transparent !important;
  border: 1px solid transparent !important;
  transition: color 120ms ease, border-color 120ms ease;
}

div[data-testid="stTabs"] button:hover{
  border-color: rgba(16,32,26,0.10) !important;
  background: rgba(255,255,255,0.35) !important;
}

div[data-testid="stTabs"] button[aria-selected="true"]{
  background: transparent !important;
  border-color: transparent !important;
  color: #004c35 !important;
  font-weight: 800 !important;
  border-bottom: 3px solid #d4af37 !important; /* gold underline */
}

div[data-testid="stTabs"] button[aria-selected="false"]{
  color: rgba(16,32,26,0.75) !important;
  font-weight: 700 !important;
  opacity: 1 !important;
}
</style>
""", unsafe_allow_html=True)


# ---------------------------
# Config loading
# ---------------------------
CFG_PATH = Path("data/config.yaml")

@st.cache_data
def load_cfg():
    with CFG_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)

cfg = load_cfg()

# ---------------------------
# Loft helpers
# ---------------------------
lofts_cfg = cfg.get("lofts_deg", {})  # e.g., {"7i": 32, "3W": 15, ...}

def loft_text_for(label: str) -> str | None:
    """Return a pretty loft string for non-wedge clubs, like '32°' or '10.5°'."""
    # Wedges already include loft in their label like "PW (46°)"
    if category_of(label) == "wedge":
        return None

    loft = lofts_cfg.get(label)
    if loft is None:
        return None

    try:
        f = float(loft)
    except Exception:
        return None

    # show 10.5° style if needed, otherwise integer like 32°
    if abs(f - round(f)) < 1e-9:
        return f"{int(round(f))}°"
    return f"{f:.1f}°"

baseline_chs0 = float(cfg["baseline"]["driver_chs_mph"])
p_shape = float(cfg["model"]["exponent_shape_p"])
rollout_cfg = cfg.get("rollout_defaults_yd", {})
wedges_cfg = cfg.get("wedges", {})
choke_sub = float(wedges_cfg.get("choke_down_subtract_yd", 4))
partials_cfg = wedges_cfg.get("partials", {})
alpha = float(partials_cfg.get("alpha", 0.55))
feel_map_cfg = partials_cfg.get("feel_map", {"75%": 0.75, "50%": 0.50, "25%": 0.25})

ui = cfg.get("ui", {})
presets = ui.get("presets", {})
default_preset = ui.get("default_preset", "My Bag")
default_bag = presets.get(default_preset, ui.get("default_bag", []))

# Anchors
anchors_raw = cfg["baseline"]["anchors"]
anchors = [Anchor(
    label=a["label"],
    club_speed_mph=float(a["club_speed_mph"]),
    carry_yd=float(a["carry_yd"]),
    category=a["category"],
    loft_deg=a.get("loft_deg")
) for a in anchors_raw]
anchor_map = anchors_by_label(anchors)

catalog = build_full_catalog()

# ---------------------------
# Helper functions
# ---------------------------
def compute_baseline(label: str):
    if label in anchor_map:
        a = anchor_map[label]
        return a.club_speed_mph, a.carry_yd

    spd = estimate_club_speed(label, anchor_map)
    if spd is None:
        return None, None

    carry = estimate_carry(label, float(spd), anchor_map, anchors)
    return float(spd), float(carry)

def compute_today(label: str, chs_today: float, offset: float):
    spd0, carry0 = compute_baseline(label)
    if spd0 is None or carry0 is None:
        return None, None
    g = responsiveness_exponent(spd0, baseline_chs0, p_shape)
    carry = scaled_carry(carry0, float(chs_today), baseline_chs0, g) + float(offset)
    rollout = rollout_for(label, rollout_cfg)
    total = carry + rollout
    return carry, total

def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))

# ---------------------------
# Title
# ---------------------------
st.markdown(
    '<div class="section-title"><div class="section-dot"></div><h1 style="margin:0;">Yardage Card</h1></div>',
    unsafe_allow_html=True
)

# ---------------------------
# Controls (collapsed into expander)
# ---------------------------
with st.expander("Adjust Yardages", expanded=False):
    chs_today = st.slider("Driver CHS (mph)", 90, 135, 105, 1)

    c1, c2 = st.columns([0.9, 1.8], vertical_alignment="center")
    with c1:
        offset = st.number_input("± (yd)", -25, 25, 0, 1)
    with c2:
        preset_names = list(presets.keys()) if presets else ["My Bag"]
        preset_index = preset_names.index(default_preset) if default_preset in preset_names else 0
        preset = st.selectbox("Preset", preset_names, index=preset_index)
        bag_default = presets.get(preset, default_bag)

# If the expander hasn't run yet on first render, ensure defaults exist
if "chs_today" not in locals():
    chs_today = 105
if "offset" not in locals():
    offset = 0
if "preset" not in locals():
    preset_names = list(presets.keys()) if presets else ["My Bag"]
    preset = default_preset if default_preset in preset_names else preset_names[0]
if "bag_default" not in locals():
    bag_default = presets.get(preset, default_bag)

# ---------------------------
# Clubs shown (keep as-is)
# ---------------------------
with st.expander("Select Clubs", expanded=False):
    options = list(dict.fromkeys(catalog + bag_default))
    bag = st.multiselect("Clubs", options=options, default=bag_default)

if not bag:
    bag = bag_default

# Badges up top (always visible) — render once (after bag exists)
bag_badge = ", ".join(bag) if bag else "—"
st.markdown(
    f"""
    <div class="badges">
      <div class="badge">CHS: {chs_today} mph</div>
      <div class="badge">Offset: {offset:+.0f} yd</div>
      <div class="badge">Preset: {preset}</div>
    """,
    unsafe_allow_html=True
)

st.divider()

# ---------------------------
# Tabs (add Debug as 3rd tab)
# ---------------------------
tab_clubs, tab_wedges, tab_debug = st.tabs(["Clubs", "Wedges", "Debug"])

# Precompute driver carry for bar scaling
driver_carry, _ = compute_today("Driver", chs_today, offset)
max_carry = float(driver_carry) if driver_carry else 1.0

def render_card(label: str, shown: str, sub: str, fill_pct: float, gap_text: str | None = None):
    fill_pct = clamp01(fill_pct)

    loft_txt = loft_text_for(label)
    label_html = (
        f'{label} <span class="ycloft">({loft_txt})</span>'
        if loft_txt else
        f'{label}'
    )

    gap_safe = gap_text if gap_text else "&nbsp;"

    st.markdown(
        f"""
        <div class="ycard">
          <div class="yrow">
            <div class="yclub">{label_html}</div>
            <div class="yvals">{shown}</div>
          </div>
          <div class="ysub">{sub}</div>
          <div class="barwrap"><div class="barfill" style="width:{fill_pct*100:.0f}%;"></div></div>
          <div class="gapline"><span class="gappill">{gap_safe}</span></div>
        </div>
        """,
        unsafe_allow_html=True
    )

with tab_clubs:
    st.markdown('<div class="section-title"><div class="section-dot"></div><h3 style="margin:0;">Clubs</h3></div>', unsafe_allow_html=True)
    st.markdown('<div class="section-underline"></div>', unsafe_allow_html=True)

    clubs_only = [x for x in bag if category_of(x) not in ("wedge", "putter")]

    # Build once: (label, carry, total, sort_carry)
    club_vals = []
    for label in clubs_only:
        carry, total = compute_today(label, chs_today, offset)
        sort_carry = carry if carry is not None else -1e9  # no-model goes bottom
        club_vals.append((label, carry, total, sort_carry))

    # Sort by carry desc
    club_vals.sort(key=lambda x: x[3], reverse=True)
    clubs_sorted = [x[0] for x in club_vals]

    # Gap to next club in sorted list (skip no-models)
    gap_map = {}
    for i, (label, carry, total, _) in enumerate(club_vals):
        if carry is None:
            continue

        nxt_carry = None
        for j in range(i + 1, len(club_vals)):
            if club_vals[j][1] is not None:
                nxt_carry = club_vals[j][1]
                break

        if nxt_carry is not None:
            gap = carry - nxt_carry
            gap_map[label] = f"Gap to next: +{gap:.0f} yd"

    # Render two-up
    for i in range(0, len(clubs_sorted), 2):
        left, right = st.columns(2, gap="small")
        for col, label in zip([left, right], clubs_sorted[i:i+2]):
            carry, total = compute_today(label, chs_today, offset)

            if carry is None:
                shown, sub, fill, gap_txt = "—", "No model", 0.0, None
            else:
                shown = f"{carry:.0f} / {total:.0f}"
                sub = "Carry / Total"
                fill = (carry / max_carry) if max_carry else 0.0
                gap_txt = gap_map.get(label)

            with col:
                render_card(label, shown, sub, fill, gap_txt)

with tab_wedges:
    st.markdown(
        '<div class="section-title"><div class="section-dot"></div><h3 style="margin:0;">Wedges</h3></div>',
        unsafe_allow_html=True
    )
    st.markdown('<div class="section-underline"></div>', unsafe_allow_html=True)

    wedge_labels = [x for x in bag if category_of(x) == "wedge"]
    if not wedge_labels:
        wedge_labels = ["PW (46°)", "GW (50°)", "SW (56°)", "LW (60°)"]

    # Remove 100% tile: show only partials (Choke, 75, 50, 25)
    scheme = ["Choke-down", "75%", "50%", "25%"]
    pct_map = {"25%": 0.40, "50%": 0.60, "75%": 0.80}
    lbl_map = {"Choke-down": "Choke"}

    # Non-linear "feel" boost (smaller exponent => longer partials vs linear)
    PARTIAL_K = {
        "75%": 0.92,
        "50%": 0.85,
        "25%": 0.78,
    }

    def wedge_values(full_carry: float):
        vals = {}
        for k in scheme:
            if k == "Choke-down":
                vals[k] = max(0.0, full_carry - choke_sub)
            else:
                pct = float(pct_map[k])                 # your “feel map”
                exp = float(PARTIAL_K.get(k, 0.85))     # non-linear boost
                vals[k] = full_carry * (pct ** exp)
        return vals

    # Sort wedges by modeled full carry (desc)
    wedge_vals = []
    for w in wedge_labels:
        carry_full, total_full = compute_today(w, chs_today, offset)
        sort_carry = carry_full if carry_full is not None else -1e9
        wedge_vals.append((w, carry_full, total_full, sort_carry))

    wedge_vals.sort(key=lambda x: x[3], reverse=True)
    wedge_labels_sorted = [x[0] for x in wedge_vals]

    # Gap to next wedge (based on full carry)
    wedge_gap_map = {}
    for i, (label, carry_full, total_full, _) in enumerate(wedge_vals):
        if carry_full is None:
            continue

        nxt_carry = None
        for j in range(i + 1, len(wedge_vals)):
            if wedge_vals[j][1] is not None:
                nxt_carry = wedge_vals[j][1]
                break

        if nxt_carry is not None:
            gap = carry_full - nxt_carry
            wedge_gap_map[label] = f"Gap to next: +{gap:.0f} yd"

    def render_wedge_card(label: str, gap_text: str | None = None):
        carry_full, total_full = compute_today(label, chs_today, offset)

        if carry_full is None:
            shown = "—"
            sub = "No model"

            # 4-wide grid (no 100% tile)
            cells = []
            for k in scheme:
                k2 = lbl_map.get(k, k)
                cells.append(
                    f'<div class="wcell"><div class="wlab">{k2}</div><div class="wval">—</div>'
                    f'<div class="wbarwrap"><div class="wbarfill" style="width:0%;"></div></div></div>'
                )
            grid_html = f'<div class="wgrid wgrid4">{"".join(cells)}</div>'
        else:
            shown = f"{carry_full:.0f} / {total_full:.0f}"
            sub = "Full (Carry / Total)"
            vals = wedge_values(carry_full)

            cells = []
            for k in scheme:
                k2 = lbl_map.get(k, k)
                v = float(vals[k])

                # mini-bar relative to FULL carry (header)
                pct = clamp01(v / carry_full) if carry_full else 0.0
                cells.append(
                    f'<div class="wcell"><div class="wlab">{k2}</div><div class="wval">{v:.0f}</div>'
                    f'<div class="wbarwrap"><div class="wbarfill" style="width:{pct*100:.0f}%;"></div></div></div>'
                )
            grid_html = f'<div class="wgrid wgrid4">{"".join(cells)}</div>'

        # full-carry bar uses max_carry scaling
        fill = (carry_full / max_carry) if (carry_full is not None and max_carry) else 0.0

        # Always reserve the gap row height (prevents last tile being shorter)
        gap_safe = gap_text if gap_text else "&nbsp;"

        st.markdown(
            f"""
            <div class="ycard wedge">
              <div class="yrow">
                <div class="yclub">{label}</div>
                <div class="yvals">{shown}</div>
              </div>
              <div class="ysub">{sub}</div>
              <div class="barwrap"><div class="barfill" style="width:{clamp01(fill)*100:.0f}%;"></div></div>
              <div class="gapline"><span class="gappill">{gap_safe}</span></div>
              {grid_html}
            </div>
            """,
            unsafe_allow_html=True
        )

    # Render two-up
    for i in range(0, len(wedge_labels_sorted), 2):
        left, right = st.columns(2, gap="small")
        for col, label in zip([left, right], wedge_labels_sorted[i:i+2]):
            with col:
                render_wedge_card(label, gap_text=wedge_gap_map.get(label))

# ---------------------------
# Debug / Validation tab (FULL CATALOG)
# ---------------------------
with tab_debug:
    st.markdown('<div class="section-title"><div class="section-dot"></div><h3 style="margin:0;">Debug</h3></div>', unsafe_allow_html=True)
    st.markdown('<div class="section-underline"></div>', unsafe_allow_html=True)

    enable_debug = st.checkbox("Enable debug output", value=False)
    if enable_debug:
        st.markdown("### Inputs")
        st.write({
            "driver_chs_mph": chs_today,
            "offset_yd": offset,
            "preset": preset,
            "selected_clubs": len(bag),
            "catalog_clubs": len(catalog),
        })

        TH = {
            "gap_small": 4,
            "gap_large_irons": 18,
            "gap_large_woods": 25,
            "rollout_driver_max": 45,
            "rollout_driver_min": 5,
            "rollout_iron_max": 22,
            "rollout_iron_min": 0,
            "monotonic_tol": 0.1,
        }

        def bucket(label: str) -> str:
            cat = category_of(label)
            if cat == "wedge":
                return "wedge"
            if cat == "putter":
                return "putter"
            if label == "Driver":
                return "driver"
            if "Wood" in label or label.endswith("W"):
                return "wood"
            if "H" in label:
                return "hybrid"
            if "U" in label:
                return "utility"
            return "iron"

        # 1) FULL catalog table (carry/total/rollout + flags)
        st.markdown("### Modeled yardages (Full catalog)")

        rows = []
        for label in catalog:
            if category_of(label) == "putter":
                continue

            carry, total = compute_today(label, chs_today, offset)
            b = bucket(label)

            if carry is None or total is None:
                rows.append({
                    "club": label, "bucket": b,
                    "carry": None, "total": None, "rollout": None,
                    "flags": "no_model",
                    "action": "Add/verify anchor mapping or label parsing for this club."
                })
                continue

            rollout = total - carry
            flags = []
            actions = []

            if total < carry:
                flags.append("total<cary")
                actions.append("Check rollout_for() and rollout_defaults_yd in config.")

            if carry <= 0 or total <= 0:
                flags.append("non_positive")
                actions.append("Check anchors / scaling logic; carry should be positive.")

            if b in ("driver", "wood"):
                if rollout < TH["rollout_driver_min"]:
                    flags.append("rollout_low")
                    actions.append("Rollout seems low for driver/woods; check rollout_defaults_yd.")
                if rollout > TH["rollout_driver_max"]:
                    flags.append("rollout_high")
                    actions.append("Rollout seems high for driver/woods; check rollout_defaults_yd.")
            if b == "iron":
                if rollout < TH["rollout_iron_min"]:
                    flags.append("rollout_neg")
                    actions.append("Iron rollout negative; check rollout_defaults_yd.")
                if rollout > TH["rollout_iron_max"]:
                    flags.append("rollout_high")
                    actions.append("Iron rollout high; check rollout_defaults_yd.")

            rows.append({
                "club": label,
                "bucket": b,
                "carry": round(carry, 1),
                "total": round(total, 1),
                "rollout": round(rollout, 1),
                "flags": ", ".join(flags) if flags else "",
                "action": " | ".join(actions) if actions else ""
            })

        rows.sort(key=lambda r: (r["carry"] is None, -(r["carry"] or -1e9)))
        st.dataframe(rows, use_container_width=True, hide_index=True, height=380)

        # 2) Gapping checks
        st.markdown("### Gapping checks (sorted by carry)")

        modeled = [r for r in rows if r["carry"] is not None]
        gaps = []
        for i in range(len(modeled) - 1):
            a = modeled[i]
            b = modeled[i + 1]
            gap = a["carry"] - b["carry"]
            flags = []
            actions = []

            large_thr = TH["gap_large_irons"]
            if a["bucket"] in ("driver", "wood") or b["bucket"] in ("driver", "wood"):
                large_thr = TH["gap_large_woods"]

            if gap < TH["gap_small"]:
                flags.append("gap_small")
                actions.append("Clubs may be redundant/too close; verify anchors or club list.")
            if gap > large_thr:
                flags.append("gap_large")
                actions.append("Gap seems large; verify anchor curve or missing intermediate club.")

            gaps.append({
                "from": a["club"],
                "to": b["club"],
                "gap_yd": round(gap, 1),
                "flags": ", ".join(flags) if flags else "",
                "action": " | ".join(actions) if actions else ""
            })

        show_all_gaps = st.checkbox("Show all gaps (including unflagged)", value=False)
        gaps_to_show = gaps if show_all_gaps else [g for g in gaps if g["flags"]]
        st.dataframe(gaps_to_show, use_container_width=True, hide_index=True, height=360)

        # 3) Wedge partial checks
        st.markdown("### Wedge partial validation")

        scheme = ["100%", "Choke-down", "75%", "50%", "25%"]
        pct_map = {"25%": 0.40, "50%": 0.60, "75%": 0.80, "100%": 1.00}

        wedge_rows = []
        for label in catalog:
            if category_of(label) != "wedge":
                continue

            carry_full, _ = compute_today(label, chs_today, offset)
            if carry_full is None:
                wedge_rows.append({
                    "wedge": label, "full_carry": None, "flags": "no_model",
                    "action": "Add/verify wedge anchor mapping or label parsing."
                })
                continue

            vals = {}
            for k in scheme:
                if k == "Choke-down":
                    vals[k] = carry_full - choke_sub
                else:
                    vals[k] = carry_full * float(pct_map[k])

            flags = []
            actions = []

            if vals["Choke-down"] > vals["100%"]:
                flags.append("choke>100")
                actions.append("Increase choke_down_subtract_yd in config.")

            order = [vals["100%"], vals["75%"], vals["50%"], vals["25%"]]
            if not all(order[i] >= order[i+1] - TH["monotonic_tol"] for i in range(len(order)-1)):
                flags.append("partials_non_monotonic")
                actions.append("Check percent_map for wedges; ensure 100>75>50>25.")

            wedge_rows.append({
                "wedge": label,
                "full_carry": round(carry_full, 1),
                "100%": round(vals["100%"], 1),
                "Choke": round(vals["Choke-down"], 1),
                "75%": round(vals["75%"], 1),
                "50%": round(vals["50%"], 1),
                "25%": round(vals["25%"], 1),
                "flags": ", ".join(flags) if flags else "",
                "action": " | ".join(actions) if actions else ""
            })

        wedge_rows.sort(key=lambda r: (r["full_carry"] is None, -(r["full_carry"] or -1e9)))
        st.dataframe(wedge_rows, use_container_width=True, hide_index=True, height=380)

        # 4) Curve/response checks at multiple CHS points
        st.markdown("### Response check (multi-CHS sanity)")

        chs_points = st.multiselect(
            "CHS points to compare",
            options=[90, 95, 100, 105, 110, 115, 120, 125],
            default=[95, 105, 115]
        )

        top_n = st.slider("How many clubs to test (top by carry)", 5, 30, 14, 1)

        sample_labels = [r["club"] for r in modeled[:top_n]]
        sample_labels += [w for w in catalog if category_of(w) == "wedge"]

        seen = set()
        sample_labels = [x for x in sample_labels if not (x in seen or seen.add(x))]

        resp_rows = []
        for label in sample_labels:
            carries = []
            for chs in chs_points:
                c, _ = compute_today(label, float(chs), offset)
                carries.append(c)

            flags = []
            actions = []

            ok = True
            for i in range(len(carries) - 1):
                if carries[i] is None or carries[i+1] is None:
                    ok = False
                    break
                if carries[i+1] < carries[i] - TH["monotonic_tol"]:
                    ok = False
                    break

            if not ok:
                flags.append("non_monotonic_vs_chs")
                actions.append("Check responsiveness_exponent() / exponent_shape_p or speed estimation mapping.")

            if 105 in chs_points and 115 in chs_points:
                try:
                    i105 = chs_points.index(105)
                    i115 = chs_points.index(115)
                    c105 = carries[i105]
                    c115 = carries[i115]
                    if c105 is not None and c115 is not None:
                        delta = c115 - c105
                        b = bucket(label)
                        if b in ("iron", "wedge") and delta > 18:
                            flags.append("too_sensitive_105_115")
                            actions.append("Iron/wedge gain seems high; tune exponent_shape_p or category scaling.")
                except ValueError:
                    pass

            row = {"club": label, "bucket": bucket(label)}
            for chs, c in zip(chs_points, carries):
                row[f"carry@{chs}"] = None if c is None else round(c, 1)
            row["flags"] = ", ".join(flags) if flags else ""
            row["action"] = " | ".join(actions) if actions else ""
            resp_rows.append(row)

        show_all_resp = st.checkbox("Show all response rows (including unflagged)", value=False)
        resp_to_show = resp_rows if show_all_resp else [r for r in resp_rows if r["flags"]]
        st.dataframe(resp_to_show, use_container_width=True, hide_index=True, height=420)
