
"""Nordic Ski 5-Zone Calculator – v1.3
Dynamic LTHR/MaxHR zone definitions.
"""

import streamlit as st, pandas as pd, numpy as np, matplotlib.pyplot as plt
from io import StringIO, BytesIO

st.set_page_config(page_title="Nordic Zone Calc", layout="centered")
st.title("⛷️ Nordic Ski ▸ 5‑Zone Heart‑Rate Calculator")

with st.expander("📚 Quick start", expanded=False):
    st.markdown(
        """
**Steps**

1. Do a 7‑lap progressive test (Lap 1 easy → Lap 7 all‑out).  
2. Make a table with **Lap, Time, HR** (RPE optional).  
3. Paste it or upload a CSV/TAB.

Example:

```
Lap,Time,HR
1,0:03:10,134
...
```
"""
    )

# --- Upload / paste ---
sample = "Lap,Time,HR\n1,0:03:10,134"
tab_up, tab_paste = st.tabs(["📁 Upload", "✂️ Paste"])
df = None
with tab_paste:
    txt = st.text_area("Paste CSV or TAB data", value=sample, height=150)
    if txt.strip():
        sep = "\t" if "\t" in txt.splitlines()[0] else ","
        df = pd.read_csv(StringIO(txt), sep=sep)
with tab_up:
    up = st.file_uploader("Upload CSV/TAB", type=["csv","tab","tsv"])
    if up:
        sep = "\t" if up.name.endswith((".tab",".tsv")) else ","
        df = pd.read_csv(up, sep=sep)

if df is None:
    st.stop()

req = {"Lap","Time","HR"}
if req - set(df.columns):
    st.error("Missing required columns."); st.stop()
df["Lap"] = df["Lap"].astype(int)
df["HR"] = pd.to_numeric(df["HR"])

def to_sec(t):
    p = [float(x) for x in str(t).split(":")]
    return p[0]*60 + p[1] if len(p)==2 else p[0]*3600 + p[1]*60 + p[2]

if "Time_sec" not in df.columns:
    df["Time_sec"] = df["Time"].apply(to_sec)

df = df.sort_values("Lap").reset_index(drop=True)
st.subheader("📄 Data preview")
st.dataframe(df, use_container_width=True)

# --- Detect anchors ---
max_hr = int(df["HR"].max())
thr = None
inc = df["HR"].diff().fillna(0)
for i in range(2,len(inc)):
    if inc[i]>0 and inc[i-1]>0 and inc[i] < 0.5*inc[i-1]:
        thr = int(df.loc[i,"HR"]); break
thr = thr or int(0.9*max_hr)

# --- Sidebar ---
st.sidebar.header("Anchor overrides")
thr = st.sidebar.number_input("Threshold HR (LTHR)", value=thr, step=1)
max_hr = st.sidebar.number_input("Max HR (MHR)", value=max_hr, step=1)
model = st.sidebar.radio("Zone model", ["% LTHR (recommended)", "% Max HR"])

# --- Zone maths ---
def zones_lthr(t,m):
    return {"Z1":(0,t*0.85),"Z2":(t*0.85,t*0.89),
            "Z3":(t*0.89,t*0.94),"Z4":(t*0.94,t),"Z5":(t,max(t*1.15,m))}
def zones_max(m):
    return {"Z1":(0.55*m,0.70*m),"Z2":(0.70*m,0.80*m),
            "Z3":(0.80*m,0.87*m),"Z4":(0.87*m,0.92*m),"Z5":(0.92*m,m)}
zones = zones_lthr(thr,max_hr) if model.startswith("% LTHR") else zones_max(max_hr)

palette = {"Z1":"#8ecae6","Z2":"#94d2bd","Z3":"#ffd166","Z4":"#f8961e","Z5":"#ef476f"}

# Explanation + table markdown
if model.startswith("% LTHR"):
    st.markdown("**Why LTHR?**  - Personalised and stable across modalities.")
    table_md = """| Zone | % LTHR | Purpose |
|------|--------|---------|
| Z1 Recovery | <85 | Very easy |
| Z2 Endurance | 85-89 | Aerobic base |
| Z3 Sub-Threshold | 89-94 | Sweet-spot (~40 min) |
| Z4 Threshold | 94-100 | Raise LT |
| Z5 Sprint | >100 | Max bursts |"""
else:
    st.markdown("**Why Max HR?**  - Simple fallback when no threshold test available.")
    table_md = """| Zone | % Max HR | Purpose |
|------|----------|---------|
| Z1 Recovery | 55-70 | Very easy |
| Z2 Endurance | 70-80 | Aerobic base |
| Z3 High Aerobic | 80-87 | Long tempo |
| Z4 Threshold | 87-92 | Near LT |
| Z5 Sprint | >92 | Max bursts |"""

st.markdown(table_md)

zone_df = pd.DataFrame([(z,int(lo),int(hi)) for z,(lo,hi) in zones.items()],
                       columns=["Zone","Low bpm","High bpm"])
st.subheader("🎯 Zone table")
st.table(zone_df)

# --- Plot ---
st.subheader("Heart‑rate profile")
fig,ax = plt.subplots(figsize=(7,4))
for z,(lo,hi) in zones.items(): ax.axhspan(lo,hi,color=palette[z],alpha=0.25)
ax.plot(df["Lap"], df["HR"], marker="o", color="black")
for x,y in zip(df["Lap"], df["HR"]):
    ax.text(x, y+1, str(int(y)), ha="center", fontsize=8)
ax.set_xlabel("Lap"); ax.set_ylabel("HR (bpm)")
ax.set_ylim(zone_df["Low bpm"].min()-15, zone_df["High bpm"].max()+15)
ax.set_xticks(df["Lap"]); ax.grid(alpha=0.3)
st.pyplot(fig, use_container_width=True)

buf=BytesIO(); fig.savefig(buf,format="png",dpi=150,bbox_inches="tight")
st.download_button("Download graph",buf.getvalue(),"zones.png","image/png")
st.download_button("Download zones CSV",zone_df.to_csv(index=False).encode(),"zones.csv","text/csv")
