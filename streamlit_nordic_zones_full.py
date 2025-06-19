
"""Nordic Ski 5‑Zone Calculator
--------------------------------
Streamlit app that ingests CSV/TAB tables **or Garmin .fit** files,
detects lactate‑threshold HR & max HR, and builds a 5‑zone table.

* Unlimited laps
* Robust column / numeric checks
* Helper expander with zone & RPE guidance
"""

import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from io import StringIO, BytesIO

# ---------------- FIT Support -----------------
try:
    import fitdecode
    FIT_SUPPORT = True
except ImportError:
    FIT_SUPPORT = False


def parse_fit(uploaded) -> pd.DataFrame:
    """Parse Garmin .fit file into Lap, Time, HR dataframe."""
    if not FIT_SUPPORT:
        raise RuntimeError("fitdecode not installed on server.")

    laps, secs, hrs = [], [], []
    from fitdecode import FitReader, FitDataMessage, FIT_FRAME_DATA

    lap_index = 0
    with FitReader(uploaded) as fr:
        for frame in fr:
            if frame.frame_type == FIT_FRAME_DATA and isinstance(frame, FitDataMessage):
                if frame.name == "lap":
                    lap_index += 1
                    laps.append(lap_index)
                    secs.append(frame.get_value("total_timer_time") or np.nan)
                    hr = (frame.get_value("end_hr") or
                          frame.get_value("max_heart_rate") or
                          frame.get_value("avg_heart_rate") or np.nan)
                    hrs.append(hr)
    if not laps:
        raise ValueError("No lap messages found – record manual laps on your watch.")
    df = pd.DataFrame({"Lap": laps,
                       "Time_sec": secs,
                       "HR": hrs})
    df["Time"] = pd.to_timedelta(df["Time_sec"], unit="s").dt.components.apply(
        lambda r: f"{int(r.minutes):02d}:{int(r.seconds):02d}", axis=1)
    return df


# --------------- UI  --------------------------
st.set_page_config(page_title="Nordic Zone Calc", layout="centered")
st.title("🗻 Nordic Ski ▸ 5‑Zone Heart‑Rate Calculator")

with st.expander("ℹ️  Help & zone definitions", expanded=False):
    st.markdown(
        """
**Collecting data**

1. Perform a progressive test (5–8 steps).  
2. Press **lap button** each step.  
3. Export CSV/TAB **or** the raw **.fit** file and upload below.

**Required columns for CSV/TAB**

```
Lap   Time   HR   [RPE]
```

**Zones & RPE**

| Zone | % Max‑HR | Purpose | RPE |
|------|----------|---------|-----|
| 1 Recovery | 55‑70 % | Easy blood‑flow | 2‑3 |
| 2 Endurance | 70‑80 % | Aerobic base | 4‑5 |
| 3 Tempo | 80‑87 % | Sustained sub‑threshold | 6 |
| 4 Threshold | 87‑92 % | Raise LT | 7‑8 |
| 5 VO₂ / Sprint | >92 % | Power & speed | 9‑10 |
""")

sample_csv = "Lap,Time,HR\n1,0:02:40,145"

tab_up, tab_paste = st.tabs(["📁 Upload", "✂️  Paste"])
data = None

with tab_up:
    uploaded = st.file_uploader("Upload CSV / TAB / FIT", type=["csv", "tab", "tsv", "fit"])
    if uploaded:
        try:
            ext = uploaded.name.split(".")[-1].lower()
            if ext == "fit":
                data = parse_fit(uploaded)
            else:
                sep = "\t" if ext in {"tab", "tsv"} else ","
                data = pd.read_csv(uploaded, sep=sep)
        except Exception as e:
            st.error(f"File error: {e}")

with tab_paste:
    txt = st.text_area("Paste CSV/TAB table", value=sample_csv, height=150)
    if txt.strip():
        sep = "\t" if "\t" in txt.splitlines()[0] else ","
        try:
            data = pd.read_csv(StringIO(txt), sep=sep)
        except Exception as e:
            st.error(f"Parse error: {e}")

if data is None:
    st.stop()

# --------------- validation -------------------
req = {"Lap", "Time", "HR"}
if (missing := req - set(data.columns)):
    st.error(f"Missing columns: {', '.join(missing)}")
    st.stop()

try:
    data["Lap"] = data["Lap"].astype(int)
    data["HR"] = pd.to_numeric(data["HR"])
except Exception:
    st.error("'Lap' must be integer and 'HR' numeric.")
    st.stop()

# if Time_sec missing, derive
def to_sec(t):
    p = [float(x) for x in str(t).split(":")]
    return p[0]*60+p[1] if len(p)==2 else p[0]*3600+p[1]*60+p[2]

if "Time_sec" not in data.columns:
    data["Time_sec"] = data["Time"].apply(to_sec)

data = data.sort_values("Lap").reset_index(drop=True)

st.subheader("📊 Uploaded data")
st.dataframe(data, use_container_width=True)

# --------------- Threshold detection ----------
max_hr_obs = int(data["HR"].max())
thr = None
diffs = data["HR"].diff().fillna(0)
for i in range(2, len(diffs)):
    if diffs[i] > 0 and diffs[i-1] > 0 and diffs[i] < 0.5 * diffs[i-1]:
        thr = int(data.loc[i, "HR"])
        break
if thr is None:
    thr = int(0.9 * max_hr_obs)

# ---------------- sidebar --------------------
st.sidebar.header("Anchor settings")
thr = st.sidebar.number_input("Threshold HR", value=thr, step=1)
max_hr = st.sidebar.number_input("Max HR", value=max_hr_obs, step=1)
model = st.sidebar.radio("Zone model", ["% Max HR", "% Threshold HR"])

# --------------- zones -----------------------
def zones_max(m):
    return {"Z1": (0.55*m, 0.70*m),
            "Z2": (0.70*m, 0.80*m),
            "Z3": (0.80*m, 0.87*m),
            "Z4": (0.87*m, 0.92*m),
            "Z5": (0.92*m, m)}

def zones_thr(t, m):
    return {"Z1": (0, t*0.85),
            "Z2": (t*0.85, t*0.89),
            "Z3": (t*0.89, t*0.94),
            "Z4": (t*0.94, t),
            "Z5": (t, max(t*1.15, m))}

zones = zones_max(max_hr) if model.startswith("% Max") else zones_thr(thr, max_hr)
palette = {"Z1": "#8ecae6", "Z2": "#94d2bd", "Z3": "#ffd166",
           "Z4": "#f8961e", "Z5": "#ef476f"}

zone_df = pd.DataFrame([(z, int(lo), int(hi)) for z, (lo, hi) in zones.items()],
                       columns=["Zone", "Low bpm", "High bpm"])

st.subheader("Calculated zones")
st.table(zone_df)

# -------------- plot -------------------------
st.subheader("Heart‑rate profile")
fig, ax = plt.subplots(figsize=(7, 4))
for z, (lo, hi) in zones.items():
    ax.axhspan(lo, hi, color=palette[z], alpha=0.25)
ax.plot(data["Lap"], data["HR"], marker="o", color="black")
for x, y in zip(data["Lap"], data["HR"]):
    ax.text(x, y+1, str(int(y)), ha="center", fontsize=8)
ax.set_xlabel("Lap"); ax.set_ylabel("HR (bpm)")
ax.set_ylim(zone_df["Low bpm"].min()-15, zone_df["High bpm"].max()+15)
ax.set_xticks(data["Lap"])
ax.grid(alpha=0.3)
st.pyplot(fig, use_container_width=True)

buf = BytesIO(); fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
st.download_button("Download graph", buf.getvalue(), "zones.png", "image/png")
st.download_button("Zones CSV", zone_df.to_csv(index=False).encode(), "zones.csv", "text/csv")
