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
/* Kill the extra whitespace at the very top */
.block-container { padding-top: 0.15rem !important; }
header[data-testid="stHeader"] { height: 0rem !important; }
div[data-testid="stToolbar"] { visibility: hidden !important; height: 0rem !important; }
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }

/* Tighten title/caption spacing */
h1 { margin-top: 0.0rem !important; margin-bottom: 0.15rem !important; }
[data-testid="stCaptionContainer"] { margin-top: 0.0rem !important; margin-bottom: 0.5rem !important; }
</style>
""", unsafe_allow_html=True)

# ---------------------------
# Augusta / Masters-inspired theme (CSS)
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

/* tighter overall layout + cream background */
.stApp {
  background: linear-gradient(180deg, var(--cream) 0%, #ffffff 65%);
}
.block-container {
  padding-top: 0.15rem !important;
  padding-bottom: 2.5rem;
  max-width: 900px;
}
h1 { margin-bottom: 0.2rem; color: var(--ink); }
[data-testid="stCaptionContainer"] { margin-bottom: 0.6rem; color: var(--muted); }

/* remove extra top whitespace on mobile */
@media (max-width: 768px){
  .block-container { padding-left: 0.75rem; padding-right: 0.75rem; }
}

/* expander */
details summary { font-size: 0.95rem; color: var(--augusta-green); }

/* input labels */
label, .stMarkdown { color: var(--ink); }

/* divider */
hr { border-color: var(--line) !important; }

/* Cards */
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

/* Section headers with a subtle azalea accent */
.section-title{
  display:flex; align-items:center; gap:10px;
}
.section-dot{
  width:10px; height:10px; border-radius:999px;
  background: var(--azalea-pink);
  box-shadow: 0 0 0 3px rgba(232,106,163,0.20);
}

/* Wedge cards: mini grid inside same card style */
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
  color: #004c35; /* augusta green dark */
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
# Title
# ---------------------------
st.markdown('<div class="section-title"><div class="section-dot"></div><h1 style="margin:0;">Yardage Card</h1></div>', unsafe_allow_html=True)
st.caption("Tournament-mode: your modeled yardages only (no GPS, no conditions, no recommendations).")

# ---------------------------
# Controls (mobile-first)
# ---------------------------
# Row 1: CHS slider full width (default 105)
chs_today = st.slider("Driver CHS (mph)", 90, 135, 105, 1)

# Row 2: compact controls (NO view toggle; always Carry + Total)
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
# Helper functions
# ---------------------------
def compute_baseline(label: str):
    # If label is exactly an anchor, use it
    if label in anchor_map:
        a = anchor_map[label]
        return a.club_speed_mph, a.carry_yd

    # Otherwise estimate club speed then infer carry from fitted curve
    spd = estimate_club_speed(label, anchor_map)
    if spd is None:
        return None, None
    carry = estimate_carry_from_speed(spd, anchors)
    return float(spd), float(carry)

def compute_today(label: str):
    spd0, carry0 = compute_baseline(label)
    if spd0 is None or carry0 is None:
        return None, None

    g = responsiveness_exponent(spd0, baseline_chs0, p_shape)
    carry = scaled_carry(carry0, float(chs_today), baseline_chs0, g) + float(offset)
    rollout = rollout_for(label, rollout_cfg)
    total = carry + rollout
    return carry, total

def render_card(label: str, shown: str, sub: str):
    st.markdown(
        f"""
        <div class="ycard">
          <div class="yrow">
            <div class="yclub">{label}</div>
            <div class="yvals">{shown}</div>
          </div>
          <div class="ysub">{sub}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

# ---------------------------
# Tabs (Clubs / Wedges)
# ---------------------------
tab_clubs, tab_wedges = st.tabs(["Clubs", "Wedges"])

with tab_clubs:
    st.markdown('<div class="section-title"><div class="section-dot"></div><h3 style="margin:0;">Clubs</h3></div>', unsafe_allow_html=True)

    clubs_only = [x for x in bag if category_of(x) not in ("wedge", "putter")]

    # Two-up grid for phone speed (less scrolling)
    for i in range(0, len(clubs_only), 2):
        left, right = st.columns(2, gap="small")

        for col, label in zip([left, right], clubs_only[i:i+2]):
            carry, total = compute_today(label)
            if carry is None:
                shown, sub = "—", "No model"
            else:
                shown = f"{carry:.0f} / {total:.0f}"
                sub = "Carry / Total"
            with col:
                render_card(label, shown, sub)

with tab_wedges:
    st.markdown('<div class="section-title"><div class="section-dot"></div><h3 style="margin:0;">Wedges</h3></div>', unsafe_allow_html=True)

    wedge_labels = [x for x in bag if category_of(x) == "wedge"]
    if not wedge_labels:
        wedge_labels = ["PW (46°)", "GW (50°)", "SW (56°)", "LW (60°)"]

    # Order left-to-right: 100% -> 25%
    scheme = ["100%", "Choke-down", "75%", "50%", "25%"]
    pct_map = {"25%": 0.40, "50%": 0.60, "75%": 0.80, "100%": 1.00}

    def wedge_values(full_carry: float):
        vals = {}
        for k in scheme:
            if k == "Choke-down":
                vals[k] = full_carry - choke_sub
            else:
                vals[k] = full_carry * float(pct_map[k])
        return vals

    def render_wedge_card(label: str):
        carry_full, total_full = compute_today(label)
        if carry_full is None:
            shown = "—"
            sub = "No model"
            grid_html = """
              <div class="wgrid">
                <div class="wcell"><div class="wlab">100%</div><div class="wval">—</div></div>
                <div class="wcell"><div class="wlab">Choke</div><div class="wval">—</div></div>
                <div class="wcell"><div class="wlab">75%</div><div class="wval">—</div></div>
                <div class="wcell"><div class="wlab">50%</div><div class="wval">—</div></div>
                <div class="wcell"><div class="wlab">25%</div><div class="wval">—</div></div>
              </div>
            """
        else:
            # Keep the header value consistent with clubs: Carry / Total
            shown = f"{carry_full:.0f} / {total_full:.0f}"
            sub = "Full (Carry / Total)"
            vals = wedge_values(carry_full)
            lbl_map = {"Choke-down": "Choke"}
            cells = []
            for k in scheme:
                k2 = lbl_map.get(k, k)
                cells.append(
                    f'<div class="wcell"><div class="wlab">{k2}</div><div class="wval">{vals[k]:.0f}</div></div>'
                )
            grid_html = f'<div class="wgrid">{"".join(cells)}</div>'

        st.markdown(
            f"""
            <div class="ycard wedge">
              <div class="yrow">
                <div class="yclub">{label}</div>
                <div class="yvals">{shown}</div>
              </div>
              <div class="ysub">{sub}</div>
              {grid_html}
            </div>
            """,
            unsafe_allow_html=True
        )

    # Two-up layout like Clubs
    for i in range(0, len(wedge_labels), 2):
        left, right = st.columns(2, gap="small")
        for col, label in zip([left, right], wedge_labels[i:i+2]):
            with col:
                render_wedge_card(label)
