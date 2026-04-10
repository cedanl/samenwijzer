"""Uitloggen — wist de sessie en stuurt terug naar de startpagina."""

import streamlit as st

for key in list(st.session_state.keys()):
    del st.session_state[key]

st.switch_page("main.py")
