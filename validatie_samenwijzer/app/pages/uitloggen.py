"""Wist sessie en stuurt terug naar de loginpagina."""

import streamlit as st

st.session_state.clear()
st.switch_page("main.py")
