"""ChromaDB wrapper: chunks opslaan en zoeken."""

from pathlib import Path

import chromadb

COLLECTIE_NAAM = "oer_chunks"
DREMPELWAARDE = 0.7  # cosine distance; > drempel = te weinig relevant


def get_client(chroma_path: Path) -> chromadb.PersistentClient:
    return chromadb.PersistentClient(path=str(chroma_path))


def get_collection(client: chromadb.ClientAPI) -> chromadb.Collection:
    return client.get_or_create_collection(
        COLLECTIE_NAAM,
        metadata={"hnsw:space": "cosine"},
    )


def voeg_chunks_toe(collection: chromadb.Collection, chunks: list[dict]) -> None:
    """Voeg chunks toe aan de collectie.

    Elk chunk dict heeft: id, tekst, embedding, metadata.
    """
    collection.add(
        ids=[c["id"] for c in chunks],
        documents=[c["tekst"] for c in chunks],
        embeddings=[c["embedding"] for c in chunks],
        metadatas=[c["metadata"] for c in chunks],
    )


def zoek_chunks(
    collection: chromadb.Collection,
    query_embedding: list[float],
    oer_ids: list[int],
    n: int = 5,
) -> list[dict]:
    """Zoek relevante chunks gefilterd op oer_ids. Geeft lege lijst bij geen resultaten."""
    if not oer_ids:
        return []

    where = {"oer_id": {"$in": oer_ids}} if len(oer_ids) > 1 else {"oer_id": oer_ids[0]}

    try:
        resultaten = collection.query(
            query_embeddings=[query_embedding],
            n_results=n,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
    except Exception:
        return []

    chunks = []
    for tekst, meta, dist in zip(
        resultaten["documents"][0],
        resultaten["metadatas"][0],
        resultaten["distances"][0],
    ):
        if dist <= DREMPELWAARDE:
            chunks.append({"tekst": tekst, "metadata": meta, "distance": dist})
    return chunks
