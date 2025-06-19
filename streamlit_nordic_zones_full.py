"""Nordic Ski 5-Zone Calculator – v0.9 (2025-06-19)

 • Accepts CSV/TAB tables or Garmin .fit files
 • Unlimited laps
 • Detailed help on RPE, zone maths, LTHR / MHR detection
"""

import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from io import StringIO, BytesIO

# ---------- Optional FIT support ----------
try:
    import fitdecode
    FIT_OK = True
except ImportError:
    FIT_OK = False


def parse_fit(up_file) -> pd.DataFrame:
    """Return a lap DataFrame (Lap, Time, HR) from Garmin FIT"""
    if not FIT_OK:
        raise RuntimeError("fitdecode not installed")
    from fitdecode import FitReader, FitDataMessage, FIT_FRAME_DATA

    laps, secs, hrs = [], [], []
    last_record_hr = None
    lap_idx = 0

    with FitReader(up_file) as fr:
        for frame in fr:
            if frame.frame_type == FIT_FRAME_DATA and isinstance(frame, FitDataMessage):
                if frame.name == "record":
                    hr_val = frame.get_value("heart_rate")
                    if hr_val is not None:
                        last_record_hr = hr_val

                if frame.name == "lap":
                    lap_idx += 1
                    laps.append(lap_idx)
                    secs.append(frame.get_value("total_timer_time") or np.nan)
                    hr = (
                        frame.get_value("end_hr")
                        or frame.get_value("max_heart_rate")
                        or frame.get_value("avg_heart_rate")
                        or last_record_hr
                        or np.nan
                    )
                    hrs.append(hr)

    if not laps:
        raise ValueError("No lap messages found – record manual laps on watch.")

    df = pd.DataFrame({"Lap": laps, "Time_sec": secs, "HR": hrs})
    df["Time"] = (
        pd.to_timedelta(df["Time_sec"], unit="s")
        .dt.components.apply(lambda r: f"{int(r.minutes):02d}:{int(r.seconds):02d}", axis=1)
    )
    return df


# ---------- UI ----------
st.set_page_config(page_title="Nordic Zone Calc", layout="centered")
st.title("🗻 Nordic Ski ▸ 5-Zone Heart-Rate Calculator")

with st.expander("ℹ️  Help / Detailed methodology", expanded=False):
    st.markdown(
        """
### What this app does
1. Reads lap data from CSV, TAB, or Garmin **.fit**.  
2. Detects **LTHR** and **MHR** automatically (you can override).  
3. Builds 5 training zones in % Max-HR or % LTHR.  
4. Plots HR per lap with color-shaded zones.

### RPE vs. Zones

| RPE | Feel | Typical zone |
|-----|------|--------------|
| 1-2 | Very, very easy | **Z1 Recovery** |
| 3-4 | Easy conversation | **Z2 Endurance** |
| 5-6 | “Comfortably hard” | **Z3 Tempo** |
| 7-8 | Hard, 1-2-word talk | **Z4 Threshold** |
| 9-10| All-out / sprint | **Z5 VO₂ / Sprint** |

### How LTHR is detected
We track lap-to-lap HR increase (∆HR). When ∆HR drops below **50 %** of the
previous positive increment, the curve is flattening—**that HR ≈ LTHR**.

### Zone formulas (default: % Max HR)

| Zone | Low | High |
|------|-----|------|
| 1 | 55 % MHR | 70 % MHR |
| 2 | 70 % | 80 % |
| 3 | 80 % | 87 % |
| 4 | 87 % | 92 % |
| 5 | 92 % | 100 % |

Switch to **% LTHR** in the sidebar if you prefer threshold-anchored zones.
"""
    )

# ---------- Upload / paste ----------
sample = "Lap,Time,HR\n1,0:02:40,145"
tab_up, tab_paste = st.tabs(["📁 Upload", "✂️  Paste"])
df = None

with tab_up:
    up = st.file_uploader("CSV / TAB / FIT", type=["csv", "tab", "tsv", "fit"])
    if up:
        try:
            ext = up.name.split(".")[-1].lower()
            if ext == "fit":
                df = parse_fit(up)
            else:
                sep = "\t" if ext in ("tab", "tsv") else ","
                df = pd.read_csv(up, sep=sep)
        except Exception as e:
            st.error(f"File error: {e}")

with tab_paste:
    text = st.text_area("Paste table (comma or tab)", value=sample, height=150)
    if text.strip():
        sep = "\t" if "\t" in text.splitlines()[0] else ","
        try:
            df = pd.read_csv(StringIO(text), sep=sep)
        except Exception as e:
            st.error(f"Parse error: {e}")

if df is None:
    st.stop()

# ---------- Validation ----------
req = {"Lap", "Time", "HR"}
if (missing := req - set(df.columns)):
    st.error("Missing columns: " + ", ".join(missing))
    st.stop()

try:
    df["Lap"] = df["Lap"].astype(int)
    df["HR"] = pd.to_numeric(df["HR"])
except Exception:
    st.error("'Lap' must be int, 'HR' numeric.")
    st.stop()

if "Time_sec" not in df.columns:
    def to_sec(t):
        parts = [float(x) for x in str(t).split(":")]
        return parts[0] * 60 + parts[1] if len(parts) == 2 else parts[0] * 3600 + parts[1] * 60 + parts[2]

    df["Time_sec"] = df["Time"].apply(to_sec)

df = df.sort_values("Lap").reset_index(drop=True)
st.subheader("📊 Data preview")
st.dataframe(df, use_container_width=True)

# ---------- LTHR + MHR detection ----------
max_hr_obs = int(df["HR"].max())
thr = None
diffs = df["HR"].diff().fillna(0)
for i in range(2, len(diffs)):
    if diffs[i] > 0 and diffs[i - 1] > 0 and diffs[i] < 0.5 * diffs[i - 1]:
        thr = int(df.loc[i, "HR"])
        break
thr = thr or int(0.9 * max_hr_obs)

# ---------- Sidebar ----------
st.sidebar.header("Anchor overrides")
thr = st.sidebar.number_input("Threshold HR", value=thr, step=1)
max_hr = st.sidebar.number_input("Max HR", value=max_hr_obs, step=1)
model = st.sidebar.radio("Zone model", ["% Max HR", "% LTHR"])

# ---------- Zones ----------
def zones_max(M):
    return {
        "Z1": (0.55 * M, 0.70 * M),
        "Z2": (0.70 * M, 0.80 * M),
        "Z3": (0.80 * M, 0.87 * M),
        "Z4": (0.87 * M, 0.92 * M),
        "Z5": (0.92 * M, M),
    }


def zones_thr(T, M):
    return {
        "Z1": (0, T * 0.85),
        "Z2": (T * 0.85, T * 0.89),
        "Z3": (T * 0.89, T * 0.94),
        "Z4": (T * 0.94, T),
        "Z5": (T, max(T * 1.15, M)),
    }


zones = zones_max(max_hr) if model.startswith("% Max") else zones_thr(thr, max_hr)
colors = {"Z1": "#8ecae6", "Z2": "#94d2bd", "Z3": "#ffd166", "Z4": "#f8961e", "Z5": "#ef476f"}

zone_df = pd.DataFrame(
    [(z, int(lo), int(hi)) for z, (lo, hi) in zones.items()], columns=["Zone", "Low bpm", "High bpm"]
)
st.subheader("Calculated zones")
st.table(zone_df)

# ---------- Plot ----------
st.subheader("Heart-rate profile")
fig, ax = plt.subplots(figsize=(7, 4))
for z, (lo, hi) in zones.items():
    ax.axhspan(lo, hi, color=colors[z], alpha=0.25)
ax.plot(df["Lap"], df["HR"], marker="o", color="black")
for x, y in zip(df["Lap"], df["HR"]):
    ax.text(x, y + 1, str(int(y)), ha="center", fontsize=8)
ax.set_xlabel("Lap")
ax.set_ylabel("HR (bpm)")
ax.set_ylim(zone_df["Low bpm"].min() - 15, zone_df["High bpm"].max() + 15)
ax.set_xticks(df["Lap"])
ax.grid(alpha=0.3)
st.pyplot(fig, use_container_width=True)

buf = BytesIO()
fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
st.download_button("Download graph", buf.getvalue(), "zones.png", "image/png")
st.download_button("Zones CSV", zone_df.to_csv(index=False).encode(), "zones.csv", "text/csv")
