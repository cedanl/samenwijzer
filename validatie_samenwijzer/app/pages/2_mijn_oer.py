"""Student: volledig OER inzien of downloaden."""

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Mijn studiegids · De digitale gids", page_icon="📄", layout="wide")

from validatie_samenwijzer._db import get_conn  # noqa: E402
from validatie_samenwijzer.auth import vereist_student  # noqa: E402
from validatie_samenwijzer.chat import resolve_oer_pad  # noqa: E402
from validatie_samenwijzer.ingest import extraheer_tekst_html  # noqa: E402
from validatie_samenwijzer.styles import (  # noqa: E402
    CSS,
    render_footer,
    render_nav,
    render_oer_markdown,
    render_student_info,
)

st.markdown(CSS, unsafe_allow_html=True)
vereist_student()
render_nav()
render_student_info()


oer_id = st.session_state.get("oer_id")

st.subheader("📄 Mijn studiegids")
st.caption("De volledige regeling van je opleiding (officieel: de OER).")

oer = get_conn().execute("SELECT * FROM oer_documenten WHERE id = ?", (oer_id,)).fetchone()

if not oer:
    st.warning("Geen studiegids gekoppeld aan jouw profiel.")
else:
    st.caption(f"Cohort {oer['cohort']}")
    pad = resolve_oer_pad(oer["bestandspad"])

    if not pad.exists():
        st.warning(f"Bestand niet gevonden op: {pad}")
        st.info("Vraag je mentor of beheerder om het bestand te uploaden.")
    elif pad.suffix.lower() == ".pdf":
        with open(pad, "rb") as f:
            pdf_bytes = f.read()
        st.download_button(
            label="⬇️ Download studiegids als PDF",
            data=pdf_bytes,
            file_name=pad.name,
            mime="application/pdf",
        )
        st.markdown("---")
        st.pdf(pdf_bytes, height=800)
    elif pad.suffix.lower() in {".html", ".htm"}:
        tekst = extraheer_tekst_html(pad)
        st.text_area("Inhoud studiegids", tekst, height=600)
    elif pad.suffix.lower() == ".md":
        render_oer_markdown(pad.read_text(encoding="utf-8"))
    else:
        st.warning(f"Bestandstype '{pad.suffix}' wordt niet ondersteund.")
        st.info("Vraag je mentor of beheerder om het bestand te uploaden.")

render_footer()
