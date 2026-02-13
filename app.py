from pathlib import Path
import streamlit as st
import yaml

from src.catalog import build_full_catalog
from src.estimates import (
    Anchor, anchors_by_label,
    estimate_club_speed, estimate_carry_from_speed,
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
  width:10px; height:10px; border-radius:999px;
  background: var(--azalea-pink);
  box-shadow: 0 0 0 3px rgba(232,106,163,0.20);
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
  border: 1px solid rgba(16,32,26,0.12);
  background: rgba(255,255,255,0.65);
  font-size: 0.78rem;
  font-weight: 800;
  color: rgba(16,32,26,0.75);
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
}
.yrow { display:flex; justify-content: space-between; align-items: baseline; gap: 10px; }
.yclub { font-size: 1.0rem; font-weight: 800; color: var(--ink); }
.yvals { font-size: 1.18rem; font-weight: 900; color: var(--augusta-green-dark); }
.ysub  { opacity: 0.75; font-size: 0.80rem; margin-top: 2px; color: var(--muted); }

/* carry bar */
.barwrap {
  width: 100%;
  height: 7px;
  background: rgba(16,32,26,0.08);
  border-radius: 999px;
  overflow: hidden;
  margin-top: 8px;
}
.barfill {
  height: 100%;
  background: linear-gradient(90deg, var(--augusta-green), var(--augusta-green-dark));
  border-radius: 999px;
}

/* gap pill */
.gapline { margin-top: 6px; display:flex; justify-content: flex-start; }
.gappill{
  display:inline-block;
  padding: 3px 8px;
  border-radius: 999px;
  border: 1px solid rgba(16,32,26,0.10);
  background: rgba(255,255,255,0.55);
  font-size: 0.72rem;
  font-weight: 800;
  color: rgba(16,32,26,0.68);
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

/* --- Tabs: stronger contrast + clearer active state --- */
div[data-testid="stTabs"] button {
  font-weight: 900 !important;
  font-size: 0.95rem !important;
  color: rgba(16,32,26,0.75) !important;
  padding: 10px 12px !important;
}

div[data-testid="stTabs"] button[aria-selected="true"]{
  color: #004c35 !important;
  border-bottom: 3px solid #d4af37 !important;  /* gold underline */
}

div[data-testid="stTabs"] button[aria-selected="false"]{
  opacity: 1 !important; /* prevent “faded out” look */
}

/* Optional: keep tab bar visible while scrolling */
div[data-testid="stTabs"]{
  position: sticky;
  top: 0;
  z-index: 50;
  background: rgba(251,247,239,0.95);
  backdrop-filter: blur(6px);
  padding-top: 4px;
}

.ycard.wedge { padding: 10px 12px; }
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

baseline_chs0 = float(cfg["baseline"]["driver_chs_mph"])
p_shape = float(cfg["model"]["exponent_shape_p"])
rollout_cfg = cfg.get("rollout_defaults_yd", {})
wedges_cfg = cfg.get("wedges", {})
choke_sub = float(wedges_cfg.get("choke_down_subtract_yd", 4))

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
    carry = estimate_carry_from_speed(spd, anchors)
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
st.markdown('<div class="section-title"><div class="section-dot"></div><h1 style="margin:0;">Yardage Card</h1></div>', unsafe_allow_html=True)

# ---------------------------
# Controls (mobile-first)
# ---------------------------

chs_today = st.slider("Driver CHS (mph)", 90, 135, 105, 1)

c1, c2 = st.columns([0.9, 1.8], vertical_alignment="center")
with c1:
    offset = st.number_input("± (yd)", -25, 25, 0, 1)
with c2:
    preset_names = list(presets.keys()) if presets else ["My Bag"]
    preset_index = preset_names.index(default_preset) if default_preset in preset_names else 0
    preset = st.selectbox("Preset", preset_names, index=preset_index)
    bag_default = presets.get(preset, default_bag)

with st.expander("Customize clubs shown"):
    options = list(dict.fromkeys(catalog + bag_default))
    bag = st.multiselect("Clubs", options=options, default=bag_default)

if not bag:
    bag = bag_default

st.divider()

# ---------------------------
# Tabs
# ---------------------------
tab_clubs, tab_wedges = st.tabs(["Clubs", "Wedges"])

# Precompute driver carry for bar scaling
driver_carry, _ = compute_today("Driver", chs_today, offset)
max_carry = float(driver_carry) if driver_carry else 1.0

def render_card(label: str, shown: str, sub: str, fill_pct: float, gap_text: str | None = None):
    fill_pct = clamp01(fill_pct)
    gap_html = f'<div class="gapline"><span class="gappill">{gap_text}</span></div>' if gap_text else ""
    st.markdown(
        f"""
        <div class="ycard">
          <div class="yrow">
            <div class="yclub">{label}</div>
            <div class="yvals">{shown}</div>
          </div>
          <div class="ysub">{sub}</div>
          <div class="barwrap"><div class="barfill" style="width:{fill_pct*100:.0f}%;"></div></div>
          {gap_html}
        </div>
        """,
        unsafe_allow_html=True
    )

with tab_clubs:
    st.markdown('<div class="section-title"><div class="section-dot"></div><h3 style="margin:0;">Clubs</h3></div>', unsafe_allow_html=True)
    st.markdown('<div class="section-underline"></div>', unsafe_allow_html=True)

    clubs_only = [x for x in bag if category_of(x) not in ("wedge", "putter")]

    # compute carries in sorted order for gap labels
    club_vals = []
    for label in clubs_only:
        carry, total = compute_today(label, chs_today, offset)
        club_vals.append((label, carry, total))

    # gap to NEXT club (by carry), using list order
    gap_map = {}
    for idx, (label, carry, total) in enumerate(club_vals):
        if carry is None:
            continue
        # find next with carry
        nxt = None
        for j in range(idx + 1, len(club_vals)):
            if club_vals[j][1] is not None:
                nxt = club_vals[j]
                break
        if nxt and nxt[1] is not None:
            gap = carry - nxt[1]
            sign = "+" if gap >= 0 else ""
            gap_map[label] = f"Gap to next: {sign}{gap:.0f} yd"

    for i in range(0, len(clubs_only), 2):
        left, right = st.columns(2, gap="small")
        for col, label in zip([left, right], clubs_only[i:i+2]):
            carry, total = compute_today(label, chs_today, offset)
            if carry is None:
                shown, sub, fill = "—", "No model", 0.0
                gap_txt = None
            else:
                shown = f"{carry:.0f} / {total:.0f}"
                sub = "Carry / Total"
                fill = (carry / max_carry) if max_carry else 0.0
                gap_txt = gap_map.get(label)
            with col:
                render_card(label, shown, sub, fill, gap_txt)

with tab_wedges:
    st.markdown('<div class="section-title"><div class="section-dot"></div><h3 style="margin:0;">Wedges</h3></div>', unsafe_allow_html=True)
    st.markdown('<div class="section-underline"></div>', unsafe_allow_html=True)

    wedge_labels = [x for x in bag if category_of(x) == "wedge"]
    if not wedge_labels:
        wedge_labels = ["PW (46°)", "GW (50°)", "SW (56°)", "LW (60°)"]

    scheme = ["100%", "Choke-down", "75%", "50%", "25%"]
    pct_map = {"25%": 0.40, "50%": 0.60, "75%": 0.80, "100%": 1.00}
    lbl_map = {"Choke-down": "Choke"}

    def wedge_values(full_carry: float):
        vals = {}
        for k in scheme:
            if k == "Choke-down":
                vals[k] = full_carry - choke_sub
            else:
                vals[k] = full_carry * float(pct_map[k])
        return vals

    def render_wedge_card(label: str):
        carry_full, total_full = compute_today(label, chs_today, offset)

        if carry_full is None:
            shown = "—"
            sub = "No model"
            cells = []
            for k in scheme:
                k2 = lbl_map.get(k, k)
                cells.append(
                    f'<div class="wcell"><div class="wlab">{k2}</div><div class="wval">—</div><div class="wbarwrap"><div class="wbarfill" style="width:0%;"></div></div></div>'
                )
            grid_html = f'<div class="wgrid">{"".join(cells)}</div>'
        else:
            shown = f"{carry_full:.0f} / {total_full:.0f}"
            sub = "Full (Carry / Total)"
            vals = wedge_values(carry_full)

            cells = []
            for k in scheme:
                k2 = lbl_map.get(k, k)
                v = float(vals[k])
                # mini-bar relative to full carry (100% cell)
                pct = clamp01(v / carry_full) if carry_full else 0.0
                cells.append(
                    f'<div class="wcell"><div class="wlab">{k2}</div><div class="wval">{v:.0f}</div><div class="wbarwrap"><div class="wbarfill" style="width:{pct*100:.0f}%;"></div></div></div>'
                )
            grid_html = f'<div class="wgrid">{"".join(cells)}</div>'

        # wedge card includes a full-carry bar as well
        fill = (carry_full / max_carry) if (carry_full is not None and max_carry) else 0.0

        st.markdown(
            f"""
            <div class="ycard wedge">
              <div class="yrow">
                <div class="yclub">{label}</div>
                <div class="yvals">{shown}</div>
              </div>
              <div class="ysub">{sub}</div>
              <div class="barwrap"><div class="barfill" style="width:{clamp01(fill)*100:.0f}%;"></div></div>
              {grid_html}
            </div>
            """,
            unsafe_allow_html=True
        )

    for i in range(0, len(wedge_labels), 2):
        left, right = st.columns(2, gap="small")
        for col, label in zip([left, right], wedge_labels[i:i+2]):
            with col:
                render_wedge_card(label)
