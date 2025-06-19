
"""Nordic Ski 5‑Zone Calculator – Streamlit Cloud version
 * Accepts CSV, TAB, or Garmin .fit files
 * Unlimited laps, robust validation, helper text
"""

import streamlit as st
import pandas as pd, numpy as np, matplotlib.pyplot as plt
from io import StringIO, BytesIO
import re

try:
    import fitdecode
    FIT_OK = True
except ImportError:
    FIT_OK = False

st.set_page_config(page_title='Nordic Ski Zone Calc', layout='centered')
st.title('🗻 Nordic Ski • 5‑Zone Heart‑Rate Calculator')

with st.expander('ℹ️  How to collect data & what zones mean', expanded=False):
    st.markdown('''
**Field-test overview**

1. Do a progressive 5–8‑lap workout (start easy, finish all‑out).  
2. Press the **lap button** on your watch at the end of each step *or* run on a fixed 600 m lap and note splits.  
3. Export the file (CSV/TAB or **`.fit`**) and drop it below.

**Required columns**

```
Lap   Time   HR   [optional RPE]
```

* `Lap` Sequential lap number (1, 2, 3 …).  
* `Time` Lap duration `mm:ss` or `hh:mm:ss`.  
* `HR` Heart‑rate at lap finish (bpm).  
* `RPE` *(optional)* Rating of Perceived Exertion 1–10.

**Training‑zone physiology**

| Zone | % Max‑HR | Purpose | Typical RPE |
|------|---------|---------|-------------|
| 1 Recovery | 55–70 % | Blood‑flow, easy distance | 2–3 |
| 2 Endurance | 70–80 % | Aerobic base, long skis | 4–5 |
| 3 Tempo | 80–87 % | Sustainable tempo, “comfortably hard” | 6 |
| 4 Threshold | 87–92 % | Pushes lactate threshold | 7–8 |
| 5 VO₂ / Sprint | >92 % | Max aerobic, power | 9–10 |

Use **RPE** as a cross‑check: if RPE says 9 but HR sits in Zone 2, sensor or data may be wrong.
''')

# --------------------------------------------------------------------
# FIT parser helper --------------------------------------------------
def parse_fit(file) -> pd.DataFrame:
    """Return DataFrame(Lap, Time, HR) from a Garmin .fit binary."""
    if not FIT_OK:
        raise RuntimeError('fitdecode not installed on server.')
    from fitdecode import FitReader

    laps, times, hrs = [], [], []
    with FitReader(file) as fr:
        lap_count = 0
        for msg in fr.read():
            if msg.name == 'lap':
                lap_count += 1
                laps.append(lap_count)
                times.append(msg.get_value('total_timer_time') or np.nan)
                hrs.append(msg.get_value('end_hr') or np.nan)

    if not laps:
        raise ValueError('No lap records found – record manual laps on your watch.')

    df = pd.DataFrame({'Lap': laps,
                       'Time_sec': times,
                       'HR': hrs})
    # convert seconds to mm:ss for display
    df['Time'] = pd.to_timedelta(df['Time_sec'], unit='s').dt.components.apply(
        lambda r: f"{int(r.minutes):02d}:{int(r.seconds):02d}", axis=1)
    return df

# --------------------------------------------------------------------
# Upload / paste interface -------------------------------------------
sample = 'Lap,Time,HR\n1,0:02:40,145'
tab_upload, tab_paste = st.tabs(['📁 Upload file', '✂️  Paste table'])
df = None

with tab_upload:
    up = st.file_uploader('CSV, TAB, or FIT (<2 MB)', type=['csv','tab','tsv','fit'])
    if up:
        if up.size > 2_000_000:
            st.error('File exceeds 2 MB – trim rows or export laps only.')
        else:
            ext = up.name.split('.')[-1].lower()
            try:
                if ext == 'fit':
                    df = parse_fit(up)
                else:
                    sep = '\t' if ext in ('tab','tsv') else ','
                    df = pd.read_csv(up, sep=sep)
            except Exception as e:
                st.error(f'Error reading file: {e}')

with tab_paste:
    text = st.text_area('Paste CSV or TAB data', value=sample, height=150)
    if text.strip():
        sep = '\t' if '\t' in text.splitlines()[0] else ','
        try:
            df = pd.read_csv(StringIO(text), sep=sep)
        except Exception as e:
            st.error(f'Parsing error: {e}')

if df is None:
    st.stop()

# --------------------------------------------------------------------
# Validation ---------------------------------------------------------
required = {'Lap','Time','HR'}
if missing := required - set(df.columns):
    st.error('Missing column(s): ' + ', '.join(missing))
    st.stop()

try:
    df['Lap'] = df['Lap'].astype(int)
    df['HR'] = pd.to_numeric(df['HR'])
except Exception:
    st.error('Lap must be integer; HR numeric.')
    st.stop()

# Unlimited laps – sort
df = df.sort_values('Lap').reset_index(drop=True)

# Time parsing utility
def to_sec(t):
    parts = [float(p) for p in str(t).split(':')]
    if len(parts) == 2:
        return parts[0]*60 + parts[1]
    if len(parts) == 3:
        return parts[0]*3600 + parts[1]*60 + parts[2]
    return np.nan
if 'Time_sec' not in df.columns:
    df['Time_sec'] = df['Time'].apply(to_sec)

st.subheader('📊 Uploaded data')
st.dataframe(df, use_container_width=True)

# --------------------------------------------------------------------
# Detect LTHR --------------------------------------------------------
max_hr_obs = int(df['HR'].max())
thr = None
inc = df['HR'].diff().fillna(0)
for i in range(2, len(inc)):
    if inc[i] > 0 and inc[i-1] > 0 and inc[i] < 0.5*inc[i-1]:
        thr = int(df.loc[i, 'HR']); break
if thr is None:
    thr = int(0.9*max_hr_obs)

# Sidebar adjustments
st.sidebar.header('🔧 Anchor settings')
thr = st.sidebar.number_input('Threshold HR', value=thr, step=1)
max_hr = st.sidebar.number_input('Max HR', value=max_hr_obs, step=1)
model = st.sidebar.radio('Zone model', ['% of Max HR','% of Threshold HR'])

# Build zones
def zones_max(m):
    return {'Zone 1':(0.55*m,0.70*m),
            'Zone 2':(0.70*m,0.80*m),
            'Zone 3':(0.80*m,0.87*m),
            'Zone 4':(0.87*m,0.92*m),
            'Zone 5':(0.92*m,m)}
def zones_thr(t,m):
    return {'Zone 1':(0,t*0.85),
            'Zone 2':(t*0.85,t*0.89),
            'Zone 3':(t*0.89,t*0.94),
            'Zone 4':(t*0.94,t),
            'Zone 5':(t,max(t*1.15,m))}

zones = zones_max(max_hr) if model.startswith('% of Max') else zones_thr(thr,max_hr)
palette = {'Zone 1':'#8ecae6','Zone 2':'#94d2bd','Zone 3':'#ffd166','Zone 4':'#f8961e','Zone 5':'#ef476f'}
zone_df = pd.DataFrame([(z,int(lo),int(hi)) for z,(lo,hi) in zones.items()],
                       columns=['Zone','Low bpm','High bpm'])
st.subheader('Calculated zones')
st.table(zone_df)

# Plot
st.subheader('Heart‑rate profile')
fig,ax = plt.subplots(figsize=(7,4))
for z,(lo,hi) in zones.items(): ax.axhspan(lo,hi,color=palette[z],alpha=0.25)
ax.plot(df['Lap'],df['HR'],marker='o',color='black')
for x,y in zip(df['Lap'],df['HR']): ax.text(x,y+1,str(int(y)),ha='center',fontsize=8)
ax.set_xlabel('Lap'); ax.set_ylabel('HR (bpm)')
ax.set_ylim(zone_df['Low bpm'].min()-15, zone_df['High bpm'].max()+15)
ax.set_xticks(df['Lap'])
ax.grid(alpha=0.3)
st.pyplot(fig, use_container_width=True)

# Downloads
buf = BytesIO(); fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
st.download_button('Download graph', buf.getvalue(), 'zones_plot.png', 'image/png')
st.download_button('Download zones CSV', zone_df.to_csv(index=False).encode(), 'zones.csv', 'text/csv')
