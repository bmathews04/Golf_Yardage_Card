from pathlib import Path
import pandas as pd
import streamlit as st

from src.io import load_config
from src.model import responsiveness_exponent, scaled_carry, format_num
from src.catalog import build_full_catalog

st.set_page_config(page_title="Yardage Card", layout="wide")

CFG_PATH = Path("data/config.yaml")
cfg = load_config(CFG_PATH)

baseline_driver_chs = float(cfg["baseline"]["driver_chs_mph"])
p_shape = float(cfg["model"]["exponent_shape_p"])
rollout_defaults = cfg.get("rollout_defaults_yd", {})
ui = cfg.get("ui", {})
aliases = ui.get("baseline_aliases", {})

# Build baseline lookup by label
baseline_rows = cfg["baseline"]["clubs"]
baseline_by_label = {r["label"]: r for r in baseline_rows}

# Wedge set (name + loft)
wedge_set = [w["label"] for w in cfg.get("wedges", {}).get("catalog", [])]

# Full catalog for multiselect
full_catalog = build_full_catalog()

# --- Header ---
st.title("⛳ Yardage Card")
st.caption("Tournament-mode yardage card: no GPS, no conditions, no recommendations.")

# --- Inputs ---
col1, col2, col3 = st.columns([2, 2, 2], vertical_alignment="center")

with col1:
    chs_today = st.slider("Driver CHS today (mph)", min_value=90, max_value=135, value=int(baseline_driver_chs), step=1)

with col2:
    view = st.segmented_control("View", options=["Carry", "Carry + Total"], default="Carry")

with col3:
    manual_offset = st.number_input("Manual ± (yd)", min_value=-25, max_value=25, value=0, step=1)

# Choke-down
choke_cfg = cfg.get("wedges", {}).get("choke_down", {})
cd_default = int(choke_cfg.get("subtract_yd_default", 4))
cd_min, cd_max = choke_cfg.get("allowed_range_yd", [3, 5])

c1, c2 = st.columns([1, 2], vertical_alignment="center")
with c1:
    choke_on = st.toggle("Choke-down", value=False)
with c2:
    choke_sub = st.slider("Choke-down subtract (yd)", min_value=int(cd_min), max_value=int(cd_max), value=cd_default, step=1, disabled=not choke_on)

st.divider()

# --- Clubs to display (preset + customize) ---
default_bag = ui.get("default_bag", [])
st.subheader("Bag")

preset_col, custom_col = st.columns([2, 3], vertical_alignment="center")
with preset_col:
    st.write("**Default bag loaded** (you can customize below).")

with custom_col:
    with st.expander("Customize clubs shown"):
        selected = st.multiselect(
            "Select clubs to display",
            options=sorted(set(full_catalog + default_bag + wedge_set)),
            default=default_bag,
        )
else_selected = default_bag  # if expander not used, we still show default

# If user didn’t open expander, selected variable won't exist; handle both cases.
clubs_to_show = locals().get("selected", else_selected)

# Ensure wedge labels with loft are present if in default bag
# (already are, but keep safe)
clubs_to_show = [c for c in clubs_to_show if c]

# --- Compute yardages ---
rows = []
missing = []

for label in clubs_to_show:
    base_label = aliases.get(label, label)
    b = baseline_by_label.get(base_label)

    if not b:
        # No baseline at all
        rows.append({"Club": label, "Carry": None, "Total": None, "Notes": "No baseline set"})
        missing.append(label)
        continue

    carry0 = b.get("carry_yd")
    cs0 = b.get("club_speed_mph")
    if carry0 is None or cs0 is None:
        rows.append({"Club": label, "Carry": None, "Total": None, "Notes": "Baseline incomplete"})
        missing.append(label)
        continue

    g = responsiveness_exponent(float(cs0), baseline_driver_chs, p_shape)
    carry_today = scaled_carry(float(carry0), float(chs_today), baseline_driver_chs, g)
    carry_today += float(manual_offset)
    if choke_on:
        carry_today -= float(choke_sub)

    rollout = float(rollout_defaults.get(base_label, 0))
    total_today = carry_today + rollout  # rollout held constant for now
    # manual offset already applied to carry; we keep total consistent via carry + rollout
    # choke-down applied via carry reduction above

    rows.append({
        "Club": label,
        "Carry": carry_today,
        "Total": total_today,
        "Notes": "" if label == base_label else f"Uses baseline: {base_label}"
    })

df = pd.DataFrame(rows)

# --- Display main table ---
st.subheader("Yardages")

if view == "Carry":
    out = df[["Club", "Carry", "Notes"]].copy()
else:
    out = df[["Club", "Carry", "Total", "Notes"]].copy()

# Format numbers for glanceability
for col in ["Carry", "Total"]:
    if col in out.columns:
        out[col] = out[col].apply(lambda x: None if pd.isna(x) else float(x))
        out[col] = out[col].apply(format_num)

st.dataframe(out, use_container_width=True, hide_index=True)

if missing:
    st.info("Some clubs have no baseline yet (shown as —). You can add baseline carry/club speed in data/config.yaml later.")

st.divider()

# --- Wedge partials table ---
partials = cfg.get("wedges", {}).get("partials", {})
scheme = partials.get("scheme", [])
partial_map = partials.get("carry_yd", {})

if scheme and partial_map:
    st.subheader("Wedge partials (carry)")
    prow = []
    for wedge_label, splits in partial_map.items():
        row = {"Wedge": wedge_label}
        for key in scheme:
            val = splits.get(key, None)
            # Partials do NOT scale with CHS by default (tournament-friendly & realistic).
            if val is None:
                row[key] = "—"
            else:
                v = float(val) + float(manual_offset)
                if choke_on:
                    v -= float(choke_sub)
                row[key] = f"{v:.0f}"
        prow.append(row)

    pdf = pd.DataFrame(prow)
    st.dataframe(pdf, use_container_width=True, hide_index=True)
else:
    st.info("No wedge partial scheme found in config.")
