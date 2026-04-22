"""Student: volledig OER inzien of downloaden."""

import base64
import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Mijn OER", page_icon="📄", layout="wide")

from validatie_samenwijzer._db import get_conn  # noqa: E402
from validatie_samenwijzer.auth import vereist_student  # noqa: E402
from validatie_samenwijzer.ingest import extraheer_tekst_html  # noqa: E402
from validatie_samenwijzer.styles import CSS, render_footer, render_nav  # noqa: E402

st.markdown(CSS, unsafe_allow_html=True)
vereist_student()
render_nav()

OEREN_PAD = Path(os.environ.get("OEREN_PAD", "oeren"))


oer_id = st.session_state.get("oer_id")
opleiding = st.session_state.get("opleiding", "")

st.subheader(f"📄 Mijn OER — {opleiding}")

oer = get_conn().execute("SELECT * FROM oer_documenten WHERE id = ?", (oer_id,)).fetchone()

if not oer:
    st.warning("Geen OER gekoppeld aan jouw profiel.")
else:
    st.caption(f"Crebo {oer['crebo']} · {oer['leerweg']} · Cohort {oer['cohort']}")
    pad = Path(oer["bestandspad"])

    if not pad.is_absolute():
        pad = OEREN_PAD.parent / pad

    if pad.exists() and pad.suffix.lower() == ".pdf":
        with open(pad, "rb") as f:
            pdf_bytes = f.read()
        st.download_button(
            label="⬇️ Download OER als PDF",
            data=pdf_bytes,
            file_name=pad.name,
            mime="application/pdf",
        )
        st.markdown("---")
        b64 = base64.b64encode(pdf_bytes).decode()
        st.markdown(
            f'<iframe src="data:application/pdf;base64,{b64}" '
            f'width="100%" height="800px"></iframe>',
            unsafe_allow_html=True,
        )
    elif pad.exists() and pad.suffix.lower() in {".html", ".htm"}:
        tekst = extraheer_tekst_html(pad)
        st.text_area("OER-inhoud", tekst, height=600)
    elif pad.exists() and pad.suffix.lower() == ".md":
        st.markdown(pad.read_text(encoding="utf-8"))
    else:
        st.warning(f"OER-bestand niet gevonden op: {pad}")
        st.info("Vraag je mentor of beheerder om het bestand te uploaden.")

render_footer()
