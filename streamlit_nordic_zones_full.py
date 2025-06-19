
"""Nordic Ski 5‑Zone Calculator – Streamlit Cloud version
• Accepts CSV/TAB and Garmin .fit
• Unlimited laps, auto‑detect threshold, adjust anchors
"""
import streamlit as st
import pandas as pd, numpy as np, matplotlib.pyplot as plt
from io import StringIO, BytesIO
import re

# ------------------------------------------------------------------
# Optional FIT support ---------------------------------------------
try:
    import fitdecode
    FIT_OK = True
except ImportError:
    FIT_OK = False

def parse_fit(file) -> pd.DataFrame:
    """Return Lap, Time, HR DataFrame from a Garmin FIT binary."""
    if not FIT_OK:
        raise RuntimeError("fitdecode missing on server.")
    from fitdecode import FitReader, FitDataMessage
    laps, times, hrs = [], [], []
    with FitReader(file) as fr:
        lap_idx = 0
        for msg in fr:
            if isinstance(msg, FitDataMessage) and msg.name == 'lap':
                lap_idx += 1
                laps.append(lap_idx)
                times.append(msg.get_value('total_timer_time') or np.nan)
                hr = (msg.get_value('end_hr') or msg.get_value('max_heart_rate')
                      or msg.get_value('avg_heart_rate'))
                hrs.append(hr if hr is not None else np.nan)
    if not laps:
        raise ValueError('No lap messages found – record manual laps on watch.')
    df = pd.DataFrame({'Lap': laps,
                       'Time_sec': times,
                       'HR': hrs})
    df['Time'] = pd.to_timedelta(df['Time_sec'], unit='s').dt.components.apply(
        lambda r: f"{int(r.minutes):02d}:{int(r.seconds):02d}", axis=1)
    return df

# ------------------------------------------------------------------
st.set_page_config(page_title='Nordic Zone Calc', layout='centered')
st.title('🗻 Nordic Ski ▸ 5‑Zone Heart‑Rate Calculator')

with st.expander('ℹ️  Help / zone definitions'):
    st.markdown('''
**Required columns**

```
Lap   Time   HR   [RPE]
```

* `Lap` – sequential lap number 1,2,3…  
* `Time` – lap duration `mm:ss` or `hh:mm:ss` (or seconds inside FIT).  
* `HR` – heart‑rate at lap finish (bpm).  
* `RPE` – *(optional)* perceived effort 1–10.

| Zone | % Max‑HR | Physiological target | RPE |
|------|----------|----------------------|-----|
| 1 Recovery | 55–70 % | Blood‑flow | 2–3 |
| 2 Endurance | 70–80 % | Aerobic base | 4–5 |
| 3 Tempo | 80–87 % | Comfortably hard | 6 |
| 4 Threshold | 87–92 % | Raise LT | 7–8 |
| 5 VO₂ / Sprint | >92 % | Max capacity | 9–10 |
''')

# ------------------------------------------------------------------
sample = 'Lap,Time,HR\n1,0:02:40,145'
tab_up, tab_paste = st.tabs(['📁 Upload', '✂️  Paste'])
df = None

with tab_up:
    uploaded = st.file_uploader('CSV / TAB / FIT', type=['csv','tab','tsv','fit'])
    if uploaded:
        try:
            ext = uploaded.name.split('.')[-1].lower()
            if ext == 'fit':
                df = parse_fit(uploaded)
            else:
                sep = '\t' if ext in ('tab','tsv') else ','
                df = pd.read_csv(uploaded, sep=sep)
        except Exception as e:
            st.error(f'File error: {e}')

with tab_paste:
    txt = st.text_area('Paste table here', value=sample, height=150)
    if txt.strip():
        sep = '\t' if '\t' in txt.splitlines()[0] else ','
        try:
            df = pd.read_csv(StringIO(txt), sep=sep)
        except Exception as e:
            st.error(f'Parse error: {e}')

if df is None:
    st.stop()

required = {'Lap','Time','HR'}
if missing := required - set(df.columns):
    st.error('Missing columns: ' + ', '.join(missing)); st.stop()

try:
    df['Lap'] = df['Lap'].astype(int)
    df['HR'] = pd.to_numeric(df['HR'])
except Exception:
    st.error('Lap must be int, HR numeric'); st.stop()

df = df.sort_values('Lap').reset_index(drop=True)

def to_sec(t):
    p = [float(x) for x in str(t).split(':')]
    return p[0]*60+p[1] if len(p)==2 else p[0]*3600+p[1]*60+p[2]
if 'Time_sec' not in df.columns:
    df['Time_sec'] = df['Time'].apply(to_sec)

st.subheader('📊 Data preview')
st.dataframe(df, use_container_width=True)

# -------- Threshold detection
max_hr_obs = int(df['HR'].max())
thr = None
inc = df['HR'].diff().fillna(0)
for i in range(2,len(inc)):
    if inc[i]>0 and inc[i-1]>0 and inc[i] < 0.5*inc[i-1]:
        thr = int(df.loc[i,'HR']); break
if thr is None:
    thr = int(0.9*max_hr_obs)

st.sidebar.header('Anchors')
thr = st.sidebar.number_input('Threshold HR',value=thr,step=1)
max_hr = st.sidebar.number_input('Max HR',value=max_hr_obs,step=1)
model = st.sidebar.radio('Zone model',['% Max HR','% Threshold HR'])

# -------- zones
def zones_max(m):
    return {'Z1':(0.55*m,0.70*m),'Z2':(0.70*m,0.80*m),
            'Z3':(0.80*m,0.87*m),'Z4':(0.87*m,0.92*m),'Z5':(0.92*m,m)}
def zones_thr(t,m):
    return {'Z1':(0,t*0.85),'Z2':(t*0.85,t*0.89),
            'Z3':(t*0.89,t*0.94),'Z4':(t*0.94,t),'Z5':(t,max(t*1.15,m))}
zones = zones_max(max_hr) if model.startswith('% Max') else zones_thr(thr,max_hr)
palette={'Z1':'#8ecae6','Z2':'#94d2bd','Z3':'#ffd166','Z4':'#f8961e','Z5':'#ef476f'}

zone_df = pd.DataFrame([(z,int(lo),int(hi)) for z,(lo,hi) in zones.items()],
                       columns=['Zone','Low','High'])
st.subheader('Calculated zones')
st.table(zone_df)

# -------- plot
st.subheader('Heart‑rate profile')
fig,ax = plt.subplots(figsize=(7,4))
for z,(lo,hi) in zones.items(): ax.axhspan(lo,hi,color=palette[z],alpha=0.25)
ax.plot(df['Lap'],df['HR'],marker='o',color='black')
for x,y in zip(df['Lap'],df['HR']): ax.text(x,y+1,str(int(y)),ha='center',fontsize=8)
ax.set_xlabel('Lap'); ax.set_ylabel('HR (bpm)')
ax.set_ylim(zone_df['Low'].min()-15, zone_df['High'].max()+15)
ax.set_xticks(df['Lap'])
ax.grid(alpha=0.3)
st.pyplot(fig, use_container_width=True)

buf = BytesIO(); fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
st.download_button('Download graph', buf.getvalue(), 'zones.png', 'image/png')
st.download_button('Zones CSV', zone_df.to_csv(index=False).encode(), 'zones.csv', 'text/csv')
