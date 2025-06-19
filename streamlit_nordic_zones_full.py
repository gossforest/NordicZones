
"""Nordic Ski 5‑Zone Calculator – v1.0 (LTHR‑anchored)
-------------------------------------------------------
 * Input: CSV or TAB table with columns Lap, Time, HR [,RPE]
 * Unlimited laps
 * Default zone model = %% LTHR
 * Expanded help aimed at high‑school athletes
"""


import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from io import StringIO, BytesIO

# ----------------- UI -----------------
st.set_page_config(page_title="Nordic Zone Calc", layout="centered")
st.title("⛷️ Nordic Ski ▸ 5‑Zone Heart‑Rate Calculator")

with st.expander("📚 Instructions (read me!)", expanded=False):
    st.markdown(
        '''
### What is this tool?
It turns **one progressive interval test** into your **five heart‑rate training zones.**

### Step‑by‑step: what you do
1. **Set up a 600 m (approx) loop** on foot or rollerskis.  
2. Warm‑up 10 min very easy.  
3. **Run/Ski 7 laps** getting steadily faster (Lap 1 = easy talk, Lap 7 = max sprint).  
4. Press the **lap button** each time; note **Lap time** and **Heart‑rate at finish** (watch shows it).  
5. Type or paste your table into the *Paste* tab **OR** upload a small CSV/TAB exported from Google Sheets / Excel.

Example table:

```
Lap,Time,HR,RPE
1,0:03:10,134,3
2,0:02:57,149,4
3,0:02:50,159,5
4,0:02:41,166,6
5,0:02:34,173,7
6,0:02:28,178,8
7,0:02:21,182,9
```

*Columns **must** be named `Lap`, `Time`, `HR`. `RPE` is optional.*

---

### How we find your anchors

* **Lactate‑threshold HR (LTHR)**  
  We look for the first lap where the rise in HR (∆HR) drops to **< 50 %** of the previous positive rise. This means your heart is “topping out”—classic Conconi inflection. **Your zones are anchored on this value.**

* **Max HR (MHR)**  
  Simply the highest HR we see in any lap. You can tweak both numbers in the sidebar.

---

### Zone formulas (default = % of LTHR)

| Zone | Formula | Why it matters |
|------|---------|----------------|
| **Z1 Recovery** |  &lt; 85 % LTHR | Easy blood‑flow, technique focus |
| **Z2 Endurance** | 85‑89 % LTHR | Aerobic base, long skis |
| **Z3 Tempo** | 89‑94 % | “Grey” middle – use sparingly |
| **Z4 Threshold** | 94‑100 % | Race‑pace stamina |
| **Z5 Speed / VO₂** | &gt; 100 % | Short sprints, max output |

*(If you switch to “% Max HR” in the sidebar, it re‑maps automatically.)*

---

### Quick RPE cheat‑sheet

| RPE (1‑10) | Feels like | Likely zone |
|------------|-----------|-------------|
| 2‑3 | “Could chat full sentences” | Z1 |
| 4‑5 | Easy chat, maybe puffing | Z2 |
| 6 | Short phrases only | Z3 |
| 7‑8 | 1‑2‑word answers | Z4 |
| 9‑10 | No talk, gasping | Z5 |

Use RPE to double‑check your numbers. If your watch says Zone 2 but you feel Zone 5, your sensor or data is wrong.
'''
    )

# ------------ sample table ---------------
sample = "Lap,Time,HR\n1,0:03:10,134"

tab_up, tab_paste = st.tabs(["📁 Upload CSV/TAB", "✂️  Paste table"])
df = None

with tab_paste:
    text = st.text_area("Paste your Lap,Time,HR table (comma or tab)", value=sample, height=160)
    if text.strip():
        sep = "\t" if "\t" in text.splitlines()[0] else ","
        try:
            df = pd.read_csv(StringIO(text), sep=sep)
        except Exception as e:
            st.error(f"Parse error: {e}")

with tab_up:
    up = st.file_uploader("Upload CSV or TAB exported from Sheets/Excel", type=["csv", "tab", "tsv"])
    if up:
        try:
            sep = "\t" if up.name.endswith((".tab", ".tsv")) else ","
            df = pd.read_csv(up, sep=sep)
        except Exception as e:
            st.error(f"Upload error: {e}")

if df is None:
    st.stop()

# ------------- validation -------------
req = {"Lap", "Time", "HR"}
if (missing := req - set(df.columns)):
    st.error("Missing columns: " + ", ".join(missing)); st.stop()

try:
    df["Lap"] = df["Lap"].astype(int)
    df["HR"] = pd.to_numeric(df["HR"])
except Exception:
    st.error("'Lap' must be int and 'HR' numeric"); st.stop()

def to_sec(t):
    parts = [float(x) for x in str(t).split(":")]
    return parts[0]*60+parts[1] if len(parts)==2 else parts[0]*3600+parts[1]*60+parts[2]

if "Time_sec" not in df.columns:
    df["Time_sec"] = df["Time"].apply(to_sec)

df = df.sort_values("Lap").reset_index(drop=True)
st.subheader("📄 Data preview")
st.dataframe(df, use_container_width=True)

# ------------- detect anchors ----------
max_hr_obs = int(df["HR"].max())

thr = None
inc = df["HR"].diff().fillna(0)
for i in range(2, len(inc)):
    if inc[i] > 0 and inc[i-1] > 0 and inc[i] < 0.5 * inc[i-1]:
        thr = int(df.loc[i, "HR"]); break
thr = thr or int(0.9*max_hr_obs)

# ------------- sidebar tweaks ----------
st.sidebar.header("Anchor overrides")
thr = st.sidebar.number_input("Threshold HR (LTHR)", value=thr, step=1)
max_hr = st.sidebar.number_input("Max HR (MHR)", value=max_hr_obs, step=1)
model = st.sidebar.radio("Zone model", ["% LTHR (default)", "% Max HR"])

# ------------- build zones -------------
def zones_lthr(t, m):
    return {"Z1": (0, t*0.85),
            "Z2": (t*0.85, t*0.89),
            "Z3": (t*0.89, t*0.94),
            "Z4": (t*0.94, t),
            "Z5": (t, max(t*1.15, m))}
def zones_max(m):
    return {"Z1":(0.55*m,0.70*m),"Z2":(0.70*m,0.80*m),
            "Z3":(0.80*m,0.87*m),"Z4":(0.87*m,0.92*m),"Z5":(0.92*m,m)}

zones = zones_lthr(thr, max_hr) if model.startswith("% LTHR") else zones_max(max_hr)
palette = {"Z1":"#8ecae6","Z2":"#94d2bd","Z3":"#ffd166","Z4":"#f8961e","Z5":"#ef476f"}

zone_df = pd.DataFrame([(z,int(lo),int(hi)) for z,(lo,hi) in zones.items()],
                       columns=["Zone","Low bpm","High bpm"])
st.subheader("🎯 Your personal zones")
st.table(zone_df)

# ------------- plot --------------------
st.subheader("Heart‑rate profile")
fig, ax = plt.subplots(figsize=(7,4))
for z,(lo,hi) in zones.items():
    ax.axhspan(lo, hi, color=palette[z], alpha=0.25)
ax.plot(df["Lap"], df["HR"], marker="o", color="black")
for x,y in zip(df["Lap"], df["HR"]):
    ax.text(x, y+1, str(int(y)), ha="center", fontsize=8)
ax.set_xlabel("Lap")
ax.set_ylabel("HR (bpm)")
ax.set_ylim(zone_df["Low bpm"].min()-15, zone_df["High bpm"].max()+15)
ax.set_xticks(df["Lap"])
ax.grid(alpha=0.3)
st.pyplot(fig, use_container_width=True)

buf = BytesIO(); fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
st.download_button("Download graph", buf.getvalue(), "zones.png", "image/png")
st.download_button("Download zones CSV", zone_df.to_csv(index=False).encode(), "zones.csv", "text/csv")
