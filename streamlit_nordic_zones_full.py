
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from io import StringIO, BytesIO

st.set_page_config(page_title="Nordic Ski Zone Calculator", layout="centered")

st.title("🗻 Nordic Ski • 5‑Zone Heart‑Rate Calculator")

st.markdown(
"""
**Required columns (CSV or TAB)**  

```
Lap   Time   HR   [optional RPE]
```

*Time may be `mm:ss` or `hh:mm:ss`.  
Upload a file **or** paste table text (comma‑ or tab‑delimited).*
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
    txt = st.text_area("Paste CSV or TSV", value=sample_tsv, height=180)
    if txt.strip():
        sep = "\t" if "\t" in txt.splitlines()[0] else ","
        df = pd.read_csv(StringIO(txt), sep=sep)

if df is None:
    st.stop()

# validate columns
required = {"Lap", "Time", "HR"}
if not required.issubset(df.columns):
    st.error(f"Missing required columns: {sorted(required)}")
    st.stop()

# convert Time -> seconds
def to_sec(t):
    parts = [float(p) for p in str(t).split(":")]
    return parts[0]*60 + parts[1] if len(parts)==2 else parts[0]*3600 + parts[1]*60 + parts[2]
df["Time_sec"] = df["Time"].apply(to_sec)

st.subheader("📊 Raw Data")
st.dataframe(df, use_container_width=True)

# ---------- Detect threshold & max ----------
max_hr_obs = int(df["HR"].max())

thr = None
incr = df["HR"].diff().fillna(0)
for i in range(2, len(incr)):
    if incr[i] > 0 and incr[i-1] > 0 and incr[i] < 0.5 * incr[i-1]:
        thr = int(df.loc[i, "HR"])
        break
if thr is None:
    thr = int(0.9 * max_hr_obs)

# ---------- Sidebar adjustments ----------
st.sidebar.header("Adjust anchors")
thr = int(st.sidebar.number_input("Threshold HR", value=thr))
max_hr = int(st.sidebar.number_input("Max HR", value=max_hr_obs))
model = st.sidebar.selectbox("Zone model", ["% of Max HR", "% of Threshold HR"])

# ---------- Build zones ----------
if model.startswith("% of Max"):
    zones = {"Zone 1":(0.55*max_hr,0.70*max_hr),
             "Zone 2":(0.70*max_hr,0.80*max_hr),
             "Zone 3":(0.80*max_hr,0.87*max_hr),
             "Zone 4":(0.87*max_hr,0.92*max_hr),
             "Zone 5":(0.92*max_hr,max_hr)}
else:
    zones = {"Zone 1":(0,0.85*thr),
             "Zone 2":(0.85*thr,0.89*thr),
             "Zone 3":(0.89*thr,0.94*thr),
             "Zone 4":(0.94*thr,thr),
             "Zone 5":(thr,max(thr*1.15,max_hr))}

colors = {"Zone 1":"#8ecae6","Zone 2":"#94d2bd","Zone 3":"#ffd166","Zone 4":"#f8961e","Zone 5":"#ef476f"}

zone_df = pd.DataFrame([(z,int(lo),int(hi)) for z,(lo,hi) in zones.items()],
                       columns=["Zone","Low bpm","High bpm"])
st.subheader("Calculated Zones")
st.table(zone_df)

# ---------- Plot ----------
st.subheader("Heart‑rate per Lap")
fig, ax = plt.subplots(figsize=(7,4))
for z,(lo,hi) in zones.items():
    ax.axhspan(lo, hi, color=colors[z], alpha=0.25)
ax.plot(df["Lap"], df["HR"], marker="o", color="black")
for x,y in zip(df["Lap"], df["HR"]):
    ax.text(x, y+1, str(int(y)), ha="center", fontsize=8)

ax.set_xlabel("Lap")
ax.set_ylabel("Heart Rate (bpm)")
ax.set_ylim(zone_df["Low bpm"].min()-15, zone_df["High bpm"].max()+15)
ax.set_xticks(df["Lap"])
ax.grid(alpha=0.3)

st.pyplot(fig, use_container_width=True)

buf = BytesIO(); fig.savefig(buf, format="png", dpi=150, bbox_inches='tight')
st.download_button("Download graph", buf.getvalue(), "zones_plot.png", "image/png")
st.download_button("Download zones CSV", zone_df.to_csv(index=False).encode(), "zones.csv", "text/csv")
