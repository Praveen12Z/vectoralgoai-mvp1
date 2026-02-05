# app.py - Streamlit entrypoint for VectorAlgoAI MVP

import streamlit as st
from core.mvp_dashboard import run_mvp_dashboard

st.set_page_config(
    page_title="VectorAlgoAI – Strategy Crash-Test Lab",
    page_icon="💹",
    layout="wide",
)

# Optional: quick debug line (remove after first successful deploy)
# st.write("App loaded successfully from root. Using numpy >= 2.0")

run_mvp_dashboard()
