import streamlit as st
import pandas as pd, numpy as np, matplotlib.pyplot as plt
from io import StringIO, BytesIO
st.set_page_config(page_title='Nordic Zone Calc')
st.title('🗻 Nordic Ski 5‑Zone Calculator')
st.markdown('Upload CSV or TAB with **Lap, Time, HR [,RPE]**.')
sample='Lap,Time,HR\n1,0:02:40,145'
up=st.file_uploader('file',type=['csv','tab','tsv']); txt=st.text_area('or paste',sample)
df=None
if up: df=pd.read_csv(up,sep='\t' if up.name.endswith('.tab') else ',')
elif txt.strip(): df=pd.read_csv(StringIO(txt),sep='\t' if '\t' in txt else ',')
if df is None: st.stop()
for col in ['Lap','Time','HR']: 
    if col not in df.columns: st.error(f'missing {col}'); st.stop()
df['Lap']=df['Lap'].astype(int); df['HR']=pd.to_numeric(df['HR'])
def sec(t): p=[float(x) for x in str(t).split(':')]; return p[0]*60+p[1] if len(p)==2 else p[0]*3600+p[1]*60+p[2]
df['Time_sec']=df['Time'].apply(sec)
max_hr=int(df['HR'].max())
thr=int(0.9*max_hr)
st.sidebar.number_input('Threshold HR',value=thr,key='thr')
st.sidebar.number_input('Max HR',value=max_hr,key='mx')
thr=st.session_state['thr']; mx=st.session_state['mx']
zones={'Z1':(0.55*mx,0.70*mx),'Z2':(0.70*mx,0.80*mx),
       'Z3':(0.80*mx,0.87*mx),'Z4':(0.87*mx,0.92*mx),'Z5':(0.92*mx,mx)}
colors={'Z1':'#8ecae6','Z2':'#94d2bd','Z3':'#ffd166','Z4':'#f8961e','Z5':'#ef476f'}
st.table(pd.DataFrame([(z,int(lo),int(hi)) for z,(lo,hi) in zones.items()],columns=['Zone','Low','High']))
fig,ax=plt.subplots(); 
for z,(lo,hi) in zones.items(): ax.axhspan(lo,hi,color=colors[z],alpha=0.3)
ax.plot(df['Lap'],df['HR'],marker='o'); st.pyplot(fig)
