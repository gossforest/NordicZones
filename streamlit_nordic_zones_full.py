
"""Nordic Zones – Streamlit with FIT support (fixed FitReader loop)"""
import streamlit as st, pandas as pd, numpy as np, matplotlib.pyplot as plt
from io import StringIO, BytesIO
import re

try:
    import fitdecode
    FIT_OK = True
except ImportError:
    FIT_OK = False

def parse_fit(file) -> pd.DataFrame:
    if not FIT_OK:
        raise RuntimeError('fitdecode not installed.')
    from fitdecode import FitReader, FitDataMessage
    laps, times, hrs = [], [], []
    with FitReader(file) as fr:
        i = 0
        for msg in fr:
            if isinstance(msg, FitDataMessage) and msg.name == 'lap':
                i += 1
                laps.append(i)
                times.append(msg.get_value('total_timer_time') or np.nan)
                hr = msg.get_value('end_hr') or msg.get_value('max_heart_rate') or msg.get_value('avg_heart_rate')
                hrs.append(hr if hr is not None else np.nan)
    if not laps:
        raise ValueError('No lap records found – be sure to record laps.')
    df = pd.DataFrame({'Lap': laps, 'Time_sec': times, 'HR': hrs})
    df['Time'] = pd.to_timedelta(df['Time_sec'], unit='s').dt.components.apply(
        lambda r: f"{int(r.minutes):02d}:{int(r.seconds):02d}", axis=1)
    return df

# ------------- UI and rest of logic omitted for brevity -------------
