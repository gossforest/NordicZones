
import streamlit as st, pandas as pd, numpy as np, matplotlib.pyplot as plt
from io import StringIO, BytesIO

st.set_page_config(page_title="Nordic Zone Calc", layout="centered")
st.title("⛷️ Nordic Ski ▸ 5‑Zone Heart‑Rate Calculator")

with st.expander("📚 How‑to & learning zone", expanded=False):
    st.markdown('\n### 1\u202f·\u202fWhy do this test?\n\nIf you train **too easy** you never get faster; too hard, you burn out.  \nHeart‑rate zones let you aim every workout at the *right* energy system.\n\n### 2\u202f·\u202fWhat is the 7‑Lap Progressive Test?\n\n| Lap | Effort cue | Goal |\n|-----|------------|------|\n| 1 | Super easy jog / ski | Warm into motion |\n| 2 | Comfortable | Could chat in sentences |\n| 3 | Steady | Hear your breath, still controlled |\n| 4 | Brisk | Short phrases only |\n| 5 | Hard | 10\u202fkm race feel |\n| 6 | Very hard | 3\u202fkm race feel |\n| 7 | All‑out | Give it everything |\n\n*Lap distance:* 600\xa0m track loop, or a known GPS loop.  \n*Record after **each lap***: **Lap time** (`mm:ss`) and **Heart‑rate** shown on your watch **right at the finish line**.\n\n### 3\u202f·\u202fRPE\xa0(Perceived Effort) Scale\n\n| RPE | Feeling | Talking test | Typical zone |\n|-----|---------|--------------|--------------|\n| 1 | Walking | Singing | — |\n| 2–3 | Very easy | Full sentences | Z1 |\n| 4–5 | Easy chat | Half sentences | Z2 |\n| 6 | Working | Short phrases | **Z3\xa0Sub‑Threshold** |\n| 7–8 | Hard | 1–2 words | Z4 |\n| 9 | Very hard | One word | Z4/Z5 |\n| 10 | Max | None | Z5 |\n\nUse RPE as a **reality‑check**: if RPE\xa0≈\xa08 but watch shows Z2, something is off (sensor drop‑outs or bad lap timing).\n\n### 4\u202f·\u202fHow this app finds your anchors\n\n* **Max\u202fHR (MHR)** – Highest HR we see in any lap.  \n* **Lactate‑Threshold\u202fHR (LTHR)** – First lap where the rise in HR per lap (∆HR) suddenly halves.  \n  *Example:*  \n  `+11\u202fbpm → +9\u202fbpm → +6\u202fbpm → +3\u202fbpm` → plateau starts → **LTHR\xa0≈ last big jump (e.g. 174\u202fbpm)**\n\n### 5\u202f·\u202fZone formulas\n\n| Zone | Default **%\u202fLTHR** | Purpose & examples |\n|------|--------------------|--------------------|\n| Z1 Recovery | <\xa085\xa0% | Easy skis, technique drills |\n| Z2 Endurance| 85–89\xa0% | Long distance, chatting pace |\n| Z3 Sub‑Threshold | 89–94\xa0% | “Sweet‑spot” interval, can hold ~40\xa0min |\n| Z4 Threshold | 94–100\xa0% | 5–10\u202fmin repeats, raise LT |\n| Z5 Sprint | >\xa0100\xa0% | Hill sprints, starts |\n\nSwitch to **%\u202fMax\u202fHR** if you don’t have a good threshold test yet (sidebar).\n\n### 6\u202f·\u202fStep‑by‑step data entry\n\n1. After your test open Google Sheets.  \n2. Make columns `Lap`, `Time` (`mm:ss`), `HR`.  \n3. Copy the block → paste it into the **Paste** tab *or* download as **CSV** and upload.\n\n### 7\u202f·\u202fInterpreting the graph\n\n* Colored bands = your zones.  \n* Black dots = HR at end of each lap.  \n* If Lap\xa01 already sits in Z3… you started too hard – repeat the test fresher!\n\n### 8\u202f·\u202fSafety tips\n\n* Test only when healthy & rested.  \n* Hydrate; warm‑up 10\u202fmin first.  \n* Chest‑strap HR monitors are more accurate than wrist sensors.\n\nNow scroll to paste/upload your table and see your zones!\n')

sample = "Lap,Time,HR\n1,0:03:10,134"
tab_up, tab_paste = st.tabs(["📁 Upload CSV/TAB", "✂️ Paste table"])
df = None
with tab_paste:
    txt = st.text_area("Paste your table", value=sample, height=170)
    if txt.strip():
        sep = "\t" if "\t" in txt.splitlines()[0] else ","
        df = pd.read_csv(StringIO(txt), sep=sep)
with tab_up:
    up = st.file_uploader("Upload CSV/TAB", type=["csv","tab","tsv"])
    if up:
        sep = "\t" if up.name.endswith(('.tab','.tsv')) else ','
        df = pd.read_csv(up, sep=sep)

if df is None:
    st.stop()

req={"Lap","Time","HR"}
if req-set(df.columns):
    st.error("Missing columns Lap, Time, HR"); st.stop()
df['Lap']=df['Lap'].astype(int)
df['HR']=pd.to_numeric(df['HR'])

def to_sec(t): p=[float(x) for x in str(t).split(':')]; return p[0]*60+p[1] if len(p)==2 else p[0]*3600+p[1]*60+p[2]
if 'Time_sec' not in df.columns: df['Time_sec']=df['Time'].apply(to_sec)
df=df.sort_values('Lap').reset_index(drop=True)

# Detect anchors
max_hr=int(df['HR'].max())
thr=None
d=df['HR'].diff().fillna(0)
for i in range(2,len(d)):
    if d[i]>0 and d[i-1]>0 and d[i] < 0.5*d[i-1]:
        thr=int(df.loc[i,'HR']); break
thr=thr or int(0.9*max_hr)

# Sidebar
st.sidebar.header("Anchor overrides")
thr=st.sidebar.number_input("Threshold HR", value=thr, step=1)
max_hr=st.sidebar.number_input("Max HR", value=max_hr, step=1)
model=st.sidebar.radio("Zone model", ["% LTHR (recommended)", "% Max HR"])

def zones_lthr(t,m): return {'Z1':(0,t*0.85),'Z2':(t*0.85,t*0.89),'Z3':(t*0.89,t*0.94),'Z4':(t*0.94,t),'Z5':(t,max(t*1.15,m))}
def zones_max(m): return {'Z1':(0.55*m,0.70*m),'Z2':(0.70*m,0.80*m),'Z3':(0.80*m,0.87*m),'Z4':(0.87*m,0.92*m),'Z5':(0.92*m,m)}
zones = zones_lthr(thr,max_hr) if model.startswith('% LTHR') else zones_max(max_hr)
palette = {'Z1':'#8ecae6','Z2':'#94d2bd','Z3':'#ffd166','Z4':'#f8961e','Z5':'#ef476f'}

zone_df=pd.DataFrame([(z,int(lo),int(hi)) for z,(lo,hi) in zones.items()], columns=['Zone','Low bpm','High bpm'])
st.subheader("🎯 Zone table (" + ("LTHR" if model.startswith('% LTHR') else 'Max HR') + ")")
st.table(zone_df)

st.subheader("Heart‑rate profile")
fig,ax=plt.subplots(figsize=(7,4))
for z,(lo,hi) in zones.items(): ax.axhspan(lo,hi,color=palette[z],alpha=0.25)
ax.plot(df['Lap'], df['HR'], marker='o', color='black')
for x,y in zip(df['Lap'], df['HR']): ax.text(x,y+1,str(int(y)),ha='center',fontsize=8)
ax.set_xlabel('Lap'); ax.set_ylabel('HR (bpm)')
ax.set_ylim(zone_df['Low bpm'].min()-15, zone_df['High bpm'].max()+15)
ax.set_xticks(df['Lap']); ax.grid(alpha=0.3)
st.pyplot(fig,use_container_width=True)

buf=BytesIO(); fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
st.download_button("Download graph", buf.getvalue(), "zones.png", "image/png")
st.download_button("Download zones CSV", zone_df.to_csv(index=False).encode(), "zones.csv", "text/csv")
