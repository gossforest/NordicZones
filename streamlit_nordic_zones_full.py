
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from io import StringIO, BytesIO

st.set_page_config(page_title="Nordic Ski Zone Calculator", layout="centered")

st.title("🗻 Nordic Ski • 5‑Zone Heart‑Rate Calculator")

st.markdown(
"""
Upload **CSV** or **TAB‑separated (.tab)** files – **headers required**:

```
Lap   Time   HR   [optional RPE]
```

*Time may be `mm:ss` or `hh:mm:ss`.  
Alternatively, paste raw text (comma‑ or tab‑delimited).*
""")

# ---------- Input ----------
sample_tsv = """Lap	Time	HR	RPE
1	0:03:06	108	3
2	0:02:59	128	4
3	0:03:01	144	5
4	0:03:08	148	6
5	0:03:42	128	4
6	0:02:40	162	8
7	0:02:24	174	10"""

tab1, tab2 = st.tabs(["Upload file", "Paste table"])
df = None
with tab1:
    up = st.file_uploader("Choose .csv or .tab", type=["csv", "tab"])
    if up:
        df = pd.read_csv(up, sep="\t" if up.name.endswith(".tab") else ",")
with tab2:
    text = st.text_area("Paste CSV or TSV", value=sample_tsv, height=180)
    if text:
        sep = "\t" if "\t" in text.splitlines()[0] else ","
        df = pd.read_csv(StringIO(text), sep=sep)

if df is None:
    st.stop()

# validate columns
req = {"Lap", "Time", "HR"}
if not req.issubset(df.columns):
    st.error(f"Missing required columns: {req}")
    st.stop()

# convert Time to seconds
def to_sec(t):
    parts = [float(x) for x in str(t).split(":")]
    return parts[0]*60 + parts[1] if len(parts)==2 else parts[0]*3600+parts[1]*60+parts[2]
df["Time_sec"] = df["Time"].apply(to_sec)

st.subheader("📊 Raw Data")
st.dataframe(df, use_container_width=True)

# derive LTHR
hr_diff = df["HR"].diff().fillna(0)
thr = None
for i in range(2, len(hr_diff)):
    if hr_diff[i]>0 and hr_diff[i-1]>0 and hr_diff[i] < 0.5*hr_diff[i-1]:
        thr = int(df.loc[i, "HR"); break]
if thr is None:
    thr = int(0.9*df["HR"].max())
max_hr = int(df["HR"].max())

# sidebar controls
st.sidebar.header("Adjust anchors")
thr = int(st.sidebar.number_input("Threshold HR", value=thr))
max_hr = int(st.sidebar.number_input("Max HR", value=max_hr))
method = st.sidebar.selectbox("Zone model", ["% of Max HR", "% of Threshold HR"])

# zones
if method.startswith("% of Max"):
    zones = {
        "Zone 1": (0.55*max_hr, 0.70*max_hr),
        "Zone 2": (0.70*max_hr, 0.80*max_hr),
        "Zone 3": (0.80*max_hr, 0.87*max_hr),
        "Zone 4": (0.87*max_hr, 0.92*max_hr),
        "Zone 5": (0.92*max_hr, max_hr)
    }
else:
    zones = {
        "Zone 1": (0, 0.85*thr),
        "Zone 2": (0.85*thr, 0.89*thr),
        "Zone 3": (0.89*thr, 0.94*thr),
        "Zone 4": (0.94*thr, 1.00*thr),
        "Zone 5": (1.00*thr, max(thr*1.15, max_hr))
    }
colors = {"Zone 1":"#8ecae6","Zone 2":"#94d2bd","Zone 3":"#ffd166","Zone 4":"#f8961e","Zone 5":"#ef476f"}

zone_df = pd.DataFrame([(z,int(lo),int(hi)) for z,(lo,hi) in zones.items()], columns=["Zone","Low bpm","High bpm"])
st.subheader("Calculated Zones")
st.table(zone_df)

# plot
st.subheader("HR per Lap")
fig, ax = plt.subplots(figsize=(7,4))
for z,(lo,hi) in zones.items():
    ax.axhspan(lo, hi, color=colors[z], alpha=0.25)
ax.plot(df["Lap"], df["HR"], marker="o", color="black")
for x,y in zip(df["Lap"], df["HR"]): ax.text(x, y+1, str(int(y)), ha="center", fontsize=8)
ax.set_xlabel("Lap"); ax.set_ylabel("bpm")
ax.set_ylim(zone_df["Low bpm"].min()-10, zone_df["High bpm"].max()+10)
ax.set_xticks(df["Lap"])
st.pyplot(fig, use_container_width=True)

buf = BytesIO(); fig.savefig(buf, format="png", dpi=150, bbox_inches='tight')
st.download_button("Download graph", buf.getvalue(), "zones_plot.png", "image/png")
st.download_button("Download zone CSV", zone_df.to_csv(index=False).encode(), "zones.csv", "text/csv")
