"""Student: volledig OER inzien of downloaden."""

import base64

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Mijn OER", page_icon="📄", layout="wide")

from validatie_samenwijzer._db import get_conn  # noqa: E402
from validatie_samenwijzer.auth import vereist_student  # noqa: E402
from validatie_samenwijzer.chat import resolve_oer_pad  # noqa: E402
from validatie_samenwijzer.ingest import extraheer_tekst_html  # noqa: E402
from validatie_samenwijzer.styles import (  # noqa: E402
    CSS,
    render_footer,
    render_nav,
    render_student_info,
)

st.markdown(CSS, unsafe_allow_html=True)
vereist_student()
render_nav()
render_student_info()


oer_id = st.session_state.get("oer_id")

st.subheader("📄 Mijn OER")

oer = get_conn().execute("SELECT * FROM oer_documenten WHERE id = ?", (oer_id,)).fetchone()

if not oer:
    st.warning("Geen OER gekoppeld aan jouw profiel.")
else:
    st.caption(f"Cohort {oer['cohort']}")
    pad = resolve_oer_pad(oer["bestandspad"])

    if not pad.exists():
        st.warning(f"OER-bestand niet gevonden op: {pad}")
        st.info("Vraag je mentor of beheerder om het bestand te uploaden.")
    elif pad.suffix.lower() == ".pdf":
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
    elif pad.suffix.lower() in {".html", ".htm"}:
        tekst = extraheer_tekst_html(pad)
        st.text_area("OER-inhoud", tekst, height=600)
    elif pad.suffix.lower() == ".md":
        st.markdown(pad.read_text(encoding="utf-8"))
    else:
        st.warning(f"Bestandstype '{pad.suffix}' wordt niet ondersteund.")
        st.info("Vraag je mentor of beheerder om het bestand te uploaden.")

render_footer()
