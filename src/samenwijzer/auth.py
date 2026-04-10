"""Toegangsbeheer: rolcontrole en mentorfiltering voor Streamlit-pagina's."""

import pandas as pd
import streamlit as st


def vereist_docent() -> None:
    """Stop de pagina als de ingelogde gebruiker geen docent is.

    Toont een foutmelding en roept st.stop() aan als de rol ontbreekt of
    niet 'docent' is. Pagina's die alleen voor docenten bedoeld zijn roepen
    dit aan direct na de CSS-injectie.
    """
    if st.session_state.get("rol") != "docent":
        st.error("🔒 Deze pagina is alleen toegankelijk voor docenten.")
        st.page_link("main.py", label="Terug naar de startpagina", icon="🏠")
        st.stop()


def mentor_filter(df: pd.DataFrame) -> pd.DataFrame:
    """Geef alleen de studenten terug die bij de ingelogde mentor horen.

    Als er geen mentor in de sessie is opgeslagen (bijv. bij een admin-rol
    zonder mentorfilter), wordt het volledige DataFrame teruggegeven.

    Args:
        df: Volledig getransformeerd studenten-DataFrame.

    Returns:
        Gefilterd DataFrame met alleen de studenten van de ingelogde mentor.
    """
    mentor_naam = st.session_state.get("mentor_naam")
    if not mentor_naam:
        return df
    return df[df["mentor"] == mentor_naam].reset_index(drop=True)
