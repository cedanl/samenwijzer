"""Samenwijzer Streamlit app.

Entry point for the interactive student learning support application.
All business logic lives in src/samenwijzer — this file only handles UI.
"""

import streamlit as st

st.set_page_config(
    page_title="Samenwijzer",
    page_icon="📚",
    layout="wide",
)

st.title("Samenwijzer")
st.write("AI en Data ter ondersteuning van studenten bij het leren.")

# TODO: implement UI components using functions from src/samenwijzer
