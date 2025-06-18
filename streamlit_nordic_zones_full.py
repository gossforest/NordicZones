
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from io import StringIO, BytesIO

st.set_page_config(page_title="Nordic Ski Zone Calculator", layout="centered")

st.title("🗻 Nordic Ski • 5‑Zone Heart‑Rate Calculator")

st.markdown(
"""
Upload **CSV** or **TAB‑separated (.tab)** files &ndash; **headers must include**:

```
Lap   Time   HR   [optional RPE]
```

*Time may be `mm:ss` or `hh:mm:ss`.  
You can also paste raw text in either comma‑ or tab‑delimited form.*
""")

# ---------- Input Section ----------
sample_tsv = """Lap	Time	HR	RPE
1	0:03:06	108	3
2	0:02:59	128	4
3	0:03:01	144	5
4	0:03:08	148	6
5	0:03:42	128	4
6	0:02:40	162	8
7	0:02:24	174	10"""

tab_upload, tab_paste = st.tabs(["Upload file", "Paste table"])
df = None
with tab_upload:
    up = st.file_uploader("Choose .csv or .tab", type=["csv", "tab"])
    if up:
        if up.name.lower().endswith(".tab"):
            df = pd.read_csv(up, sep="\t")
        else:
            df = pd.read_csv(up)

with tab_paste:
    txt = st.text_area("Paste CSV or TSV text", value=sample_tsv, height=180)
    if txt:
        # detect delimiter: tab if present, else comma
        delimiter = "\t" if "\t" in txt.splitlines()[0] else ","
        df = pd.read_csv(StringIO(txt), sep=delimiter)

if df is None:
    st.stop()

# sanity‑check required columns
required_cols = {"Lap", "Time", "HR"}
if not required_cols.issubset(set(df.columns)):
    st.error(f"Missing required columns. Found {list(df.columns)}, need at least {sorted(required_cols)}.")
    st.stop()

# ---------- Parse time column ----------
def to_sec(t):
    parts = [float(x) for x in str(t).split(":")]
    if len(parts) == 3:
        h, m, s = parts
        return h*3600 + m*60 + s
    if len(parts) == 2:
        m, s = parts
        return m*60 + s
    return np.nan

df["Time_sec"] = df["Time"].apply(to_sec)
df = df.dropna(subset=["HR"])

st.subheader("📊 Raw Data")
st.dataframe(df, use_container_width=True)

# ---------- Threshold & Max detection ----------
max_hr_observed = int(df["HR"].max())

# Detect threshold by HR increment deflection
d = df["HR"].diff().fillna(0)
thr = None
for i in range(2, len(d)):
    if d[i] > 0 and d[i-1] > 0 and d[i] < 0.5 * d[i-1]:
        thr = int(df.iloc[i]["HR"])
        break
if thr is None:
    thr = int(0.9 * max_hr_observed)

st.sidebar.header("🔧 Fine‑tune Anchors")
thr = int(st.sidebar.number_input("Threshold HR (bpm)", value=thr))
max_hr = int(st.sidebar.number_input("Maximum HR (bpm)", value=max_hr_observed))
method = st.sidebar.selectbox("Zone method", ("% of Max HR", "% of Threshold HR"))

# ---------- Build zones ----------
if method == "% of Max HR":
    zones = {
        "Zone 1": (0.55*max_hr, 0.70*max_hr),
        "Zone 2": (0.70*max_hr, 0.80*max_hr),
        "Zone 3": (0.80*max_hr, 0.87*max_hr),
        "Zone 4": (0.87*max_hr, 0.92*max_hr),
        "Zone 5": (0.92*max_hr, max_hr)
    }
else:
    zones = {
        "Zone 1": (0.00*thr, 0.85*thr),
        "Zone 2": (0.85*thr, 0.89*thr),
        "Zone 3": (0.89*thr, 0.94*thr),
        "Zone 4": (0.94*thr, 1.00*thr),
        "Zone 5": (1.00*thr, max(thr*1.15, max_hr))  # extend upper band
    }

zone_colors = {
    "Zone 1": "#8ecae6",
    "Zone 2": "#94d2bd",
    "Zone 3": "#ffd166",
    "Zone 4": "#f8961e",
    "Zone 5": "#ef476f"
}

# ---------- Zone Table ----------
zone_df = pd.DataFrame([(z, int(lo), int(hi)) for z,(lo,hi) in zones.items()],
                       columns=["Zone","Low bpm","High bpm"])

st.subheader("🟦 Calculated Zones" if method=="% of Max HR" else "🟧 Threshold‑Anchored Zones")
st.table(zone_df)

# ---------- Plot ----------
st.subheader("📈 HR per Lap with Color‑Shaded Zones")

fig, ax = plt.subplots(figsize=(7,4))
for z,(lo,hi) in zones.items():
    ax.axhspan(lo, hi, color=zone_colors[z], alpha=0.25)

ax.plot(df["Lap"], df["HR"], marker="o", color="black", linewidth=2)

for x,y in zip(df["Lap"], df["HR"]):
    ax.text(x, y+1, f"{int(y)}", ha="center", fontsize=8)

ax.set_xlabel("Lap")
ax.set_ylabel("Heart Rate (bpm)")
ax.set_ylim(zone_df["Low bpm"].min()-15, zone_df["High bpm"].max()+15)
ax.set_xticks(df["Lap"], df["Lap"].astype(str))
ax.grid(alpha=0.3)

handles = [plt.Line2D([0],[0], color=zone_colors[z], marker='s', linestyle='', markersize=10) for z in zones]
ax.legend(handles, zones.keys(), title="Zones", bbox_to_anchor=(1.02,1), loc="upper left" )

st.pyplot(fig, use_container_width=True)

buf = BytesIO()
fig.savefig(buf, format="png", dpi=150, bbox_inches='tight')
st.download_button("Download graph", buf.getvalue(), "zones_plot.png", "image/png")

st.download_button("Download zones CSV", zone_df.to_csv(index=False).encode(), "zones.csv", "text/csv")
