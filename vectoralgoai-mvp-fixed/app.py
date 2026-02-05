import streamlit as st
from core.mvp_dashboard import run_mvp_dashboard

st.set_page_config(
    page_title="VectorAlgoAI – Strategy Crash-Test Lab",
    page_icon="💹",
    layout="wide",
)

run_mvp_dashboard()