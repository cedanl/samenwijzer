import pytest
import chromadb
from validatie_samenwijzer.vector_store import get_collection, voeg_chunks_toe, zoek_chunks


@pytest.fixture
def collection():
    client = chromadb.EphemeralClient()
    return get_collection(client)


def test_get_collection_geeft_collectie_terug(collection):
    assert collection.name == "oer_chunks"


def test_voeg_chunks_toe_en_zoek(collection):
    chunks = [
        {
            "id": "chunk_001",
            "tekst": "De student volgt minimaal 800 uur BPV per jaar.",
            "embedding": [0.1] * 1536,
            "metadata": {"oer_id": 1, "instelling": "rijn", "crebo": "25655",
                         "cohort": "2025", "leerweg": "BOL", "pagina": 14},
        },
        {
            "id": "chunk_002",
            "tekst": "Vrijstelling kan worden verleend bij EVC.",
            "embedding": [0.9] * 1536,
            "metadata": {"oer_id": 2, "instelling": "aeres", "crebo": "25100",
                         "cohort": "2025", "leerweg": "BOL", "pagina": 7},
        },
    ]
    voeg_chunks_toe(collection, chunks)
    assert collection.count() == 2


def test_zoek_filtert_op_oer_id(collection):
    chunks = [
        {"id": "c1", "tekst": "BPV uren verplicht.", "embedding": [0.1] * 1536,
         "metadata": {"oer_id": 1, "instelling": "rijn", "crebo": "25655",
                      "cohort": "2025", "leerweg": "BOL", "pagina": 5}},
        {"id": "c2", "tekst": "Examen afleggen.", "embedding": [0.2] * 1536,
         "metadata": {"oer_id": 2, "instelling": "aeres", "crebo": "25100",
                      "cohort": "2025", "leerweg": "BOL", "pagina": 8}},
    ]
    voeg_chunks_toe(collection, chunks)
    resultaten = zoek_chunks(collection, query_embedding=[0.1] * 1536, oer_ids=[1], n=5)
    assert all(r["metadata"]["oer_id"] == 1 for r in resultaten)


def test_zoek_geeft_lege_lijst_bij_geen_resultaten(collection):
    resultaten = zoek_chunks(collection, query_embedding=[0.5] * 1536, oer_ids=[99], n=5)
    assert resultaten == []
