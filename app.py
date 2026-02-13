from pathlib import Path
import streamlit as st
import yaml

from src.catalog import build_full_catalog
from src.estimates import (
    Anchor, anchors_by_label,
    estimate_club_speed, estimate_carry_from_speed,
    responsiveness_exponent, scaled_carry, rollout_for, category_of, parse_loft
)

st.set_page_config(page_title="Yardage Card", layout="wide")

CFG_PATH = Path("data/config.yaml")

@st.cache_data
def load_cfg():
    with CFG_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)

cfg = load_cfg()

# --- CSS for phone-friendly cards ---
st.markdown("""
<style>
.block-container { padding-top: 0.8rem; padding-bottom: 4rem; }
div[data-testid="stMetric"] { border-radius: 16px; padding: 10px 12px; }
.ycard { padding: 14px 14px; border: 1px solid rgba(255,255,255,0.10); border-radius: 18px; margin-bottom: 10px; }
.yrow { display:flex; justify-content: space-between; gap: 10px; }
.yclub { font-size: 1.05rem; font-weight: 700; }
.yvals { font-size: 1.15rem; font-weight: 800; }
.ysub { opacity: 0.75; font-size: 0.85rem; margin-top: 2px; }
</style>
""", unsafe_allow_html=True)

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

st.title("⛳ Yardage Card")
st.caption("Tournament-mode: your modeled yardages only (no GPS, no conditions, no recommendations).")

# Inputs row
c1, c2, c3 = st.columns([2, 2, 2], vertical_alignment="center")
with c1:
    chs_today = st.slider("Driver CHS (mph)", 90, 135, int(baseline_chs0), 1)
with c2:
    view = st.segmented_control("View", ["Carry", "Carry + Total"], default="Carry")
with c3:
    offset = st.number_input("Manual ± (yd)", -25, 25, 0, 1)

# Bag preset
p1, p2 = st.columns([2, 3], vertical_alignment="center")
with p1:
    preset_names = list(presets.keys()) if presets else ["My Bag"]
    preset = st.selectbox("Preset", preset_names, index=preset_names.index(default_preset) if default_preset in preset_names else 0)
    bag_default = presets.get(preset, default_bag)
with p2:
    with st.expander("Customize clubs shown"):
        bag = st.multiselect("Clubs", options=sorted(set(catalog + bag_default)), default=bag_default)
if "bag" not in locals():
    bag = bag_default

st.divider()

# Helper: compute baseline for any label
def compute_baseline(label: str):
    # If label is exactly an anchor, use it
    if label in anchor_map:
        a = anchor_map[label]
        return a.club_speed_mph, a.carry_yd

    # Allow "3H" etc by estimating speed and then carry from fitted curve
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

# --- Clubs section (cards) ---
st.subheader("Clubs")

for label in bag:
    if label == "Putter":
        continue
    cat = category_of(label)
    if cat == "wedge":
        # show wedges in wedge section only
        continue

    carry, total = compute_today(label)
    if carry is None:
        shown = "—"
        sub = "No model"
    else:
        shown = f"{carry:.0f}" if view == "Carry" else f"{carry:.0f} / {total:.0f}"
        sub = "Carry" if view == "Carry" else "Carry / Total"

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

st.divider()

# --- Wedges section ---
st.subheader("Wedges")

# Build wedge list from whatever wedges exist in your bag; if none, show common defaults
wedge_labels = [x for x in bag if category_of(x) == "wedge"]
if not wedge_labels:
    wedge_labels = ["PW (46°)", "GW (50°)", "SW (56°)", "LW (60°)"]

partials_cfg = wedges_cfg.get("partials", {})
scheme = partials_cfg.get("scheme", ["25%", "50%", "75%", "Choke-down", "100%"])
pct_map = partials_cfg.get("percent_map", {"25%": 0.40, "50%": 0.60, "75%": 0.80, "100%": 1.00})

# Render a phone-friendly wedge table using columns
header = st.columns([2, 1, 1, 1, 1, 1], vertical_alignment="center")
header[0].markdown("**Wedge**")
for i, k in enumerate(scheme, start=1):
    header[i].markdown(f"**{k}**")

for w in wedge_labels:
    carry_full, total_full = compute_today(w)  # full swing modeled
    if carry_full is None:
        vals = ["—"] * len(scheme)
    else:
        # Build partials as fractions of the (modeled) full carry
        vals = []
        for k in scheme:
            if k == "Choke-down":
                # choke-down is full swing carry - configured subtract
                vals.append(f"{(carry_full - choke_sub):.0f}")
            else:
                frac = float(pct_map.get(k, 1.0))
                vals.append(f"{(carry_full * frac):.0f}")

    row = st.columns([2, 1, 1, 1, 1, 1], vertical_alignment="center")
    row[0].write(w)
    for i, v in enumerate(vals, start=1):
        row[i].write(v)
