import json
import chromadb
from pathlib import Path
from sentence_transformers import SentenceTransformer

# Load embedding model once at startup
embedder = SentenceTransformer("all-MiniLM-L6-v2")

# In-memory ChromaDB client (no server needed)
chroma_client = chromadb.Client()

def _get_collection(name: str):
    return chroma_client.get_or_create_collection(name=name)

def ingest_jobs(jobs: list):
    """Load jobs into ChromaDB for semantic retrieval."""
    col = _get_collection("jobs")
    if col.count() > 0:
        return
    docs = [f"{j['title']} at {j['company']}. Required: {', '.join(j['required_skills'])}. {j.get('description','')}" for j in jobs]
    ids = [str(j["id"]) for j in jobs]
    metadatas = [{"title": j["title"], "location": j["location"]} for j in jobs]
    embeddings = embedder.encode(docs).tolist()
    col.add(documents=docs, ids=ids, metadatas=metadatas, embeddings=embeddings)

def search_jobs(query: str, n_results: int = 5) -> list:
    """Return top-N semantically similar job IDs."""
    col = _get_collection("jobs")
    if col.count() == 0:
        return []
    q_emb = embedder.encode([query]).tolist()
    results = col.query(query_embeddings=q_emb, n_results=min(n_results, col.count()))
    return [int(i) for i in results["ids"][0]]

def load_jobs_from_json(path: str) -> list:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)