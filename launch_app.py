
import os, sys, webbrowser, threading
import streamlit.web.cli as stcli
from pathlib import Path

os.environ["STREAMLIT_GLOBAL_DEVELOPMENTMODE"] = "false"

APP_FILE = Path(__file__).with_name("streamlit_nordic_zones_full.py")

def open_browser():
    webbrowser.open("http://localhost:8501")

def main():
    threading.Timer(2, open_browser).start()
    sys.argv = ["streamlit", "run", str(APP_FILE)]
    sys.exit(stcli.main())

if __name__ == "__main__":
    main()
