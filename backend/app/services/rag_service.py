"""Persistent Chroma retrieval with an offline local vector fallback."""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_client = None
_embedder = None
_collections = {}
EMBEDDING_BACKEND = "unavailable"

class HashingEmbedder:
    """Deterministic local bag-of-words/bigrams vectorizer for offline startup."""
    def __init__(self):
        from sklearn.feature_extraction.text import HashingVectorizer
        self.vectorizer = HashingVectorizer(n_features=384, alternate_sign=False, norm="l2", ngram_range=(1, 2), stop_words="english")
    def encode(self, values, normalize_embeddings=True):
        return self.vectorizer.transform(values).toarray()

def _load_stack():
    global _client, _embedder, EMBEDDING_BACKEND
    if _client is not None:
        return True
    try:
        import chromadb
        _client = chromadb.PersistentClient(path=str(ROOT / "data" / "chroma"))
        local_model = os.getenv("CAREERFLOW_EMBEDDING_MODEL", "")
        if local_model and Path(local_model).exists():
            try:
                from sentence_transformers import SentenceTransformer
                _embedder = SentenceTransformer(local_model)
                EMBEDDING_BACKEND = "local sentence-transformers model"
            except Exception:
                _embedder = HashingEmbedder()
                EMBEDDING_BACKEND = "offline hashing vectors"
        else:
            _embedder = HashingEmbedder()
            EMBEDDING_BACKEND = "offline hashing vectors"
        return True
    except Exception:
        _client = None
        _embedder = None
        EMBEDDING_BACKEND = "unavailable"
        return False

def _collection(name):
    if not _load_stack(): return None
    if name not in _collections:
        _collections[name] = _client.get_or_create_collection(name=name, metadata={"hnsw:space":"cosine"})
    return _collections[name]

def load_jobs_from_json(path):
    with open(path,"r",encoding="utf-8") as file: return json.load(file)

def _knowledge_documents():
    filenames={"jobs":"jobs.json","skills":"skills.json","interviews":"interviews.json","careers":"careers.json","learning":"learning.json"}
    docs=[]
    for kind,filename in filenames.items():
        path=ROOT/"data"/filename
        if not path.exists(): continue
        try: rows=json.loads(path.read_text(encoding="utf-8"))
        except (OSError,json.JSONDecodeError): continue
        for row in rows:
            if not isinstance(row,dict): continue
            text=" ".join(str(v) for k,v in row.items() if isinstance(v,(str,int,float,list)) and k!="source_url")
            if text.strip(): docs.append((kind,str(row.get("id",f"{kind}-{len(docs)}")),text,row))
    return docs

def ingest_knowledge():
    """Vectorize and upsert curated documents in separate Chroma collections."""
    if not _load_stack(): return {"available":False,"documents":0,"embedding_backend":EMBEDDING_BACKEND}
    grouped={}
    for kind,identifier,text,metadata in _knowledge_documents(): grouped.setdefault(kind,[]).append((identifier,text,metadata))
    count=0
    for kind,rows in grouped.items():
        col=_collection(kind);ids=[x[0] for x in rows];documents=[x[1] for x in rows]
        metas=[{"source_type":kind,"title":str(m.get("title",m.get("name",kind))),"role":str(m.get("title","")),"location":str(m.get("location","")),"source_url":str(m.get("source_url",""))} for _,_,m in rows]
        vectors=_embedder.encode(documents,normalize_embeddings=True).tolist()
        col.upsert(ids=ids,documents=documents,metadatas=metas,embeddings=vectors);count+=len(rows)
    return {"available":True,"documents":count,"embedding_backend":EMBEDDING_BACKEND}

def search_knowledge(query,category="jobs",n_results=5):
    col=_collection(category)
    if col is None or col.count()==0: return [],[]
    vectors=_embedder.encode([query],normalize_embeddings=True).tolist()
    result=col.query(query_embeddings=vectors,n_results=min(max(1,n_results),col.count()),include=["distances"])
    ids=result.get("ids",[[]])[0];distances=result.get("distances",[[]])[0]
    return [str(i) for i in ids],[max(0.0,1.0-float(d)) for d in distances]

def search_jobs(query,n_results=5):
    ids,_=search_knowledge(query,"jobs",n_results)
    try:return [int(i) for i in ids]
    except ValueError:return []

def retrieve_context(query, categories=("jobs",), limit=3):
    """Retrieve relevant text chunks and source metadata from Chroma."""
    found=[]
    for category in categories:
        col=_collection(category)
        if col is None or col.count()==0: continue
        vector=_embedder.encode([query],normalize_embeddings=True).tolist()
        rows=col.query(query_embeddings=vector,n_results=min(max(1,limit),col.count()),include=["documents","metadatas","distances"])
        for i,doc in enumerate(rows.get("documents",[[]])[0]):
            meta=rows.get("metadatas",[[]])[0][i] or {}
            distance=rows.get("distances",[[]])[0][i]
            found.append({"text":doc,"source_type":meta.get("source_type",category),"title":meta.get("title",category),"source_url":meta.get("source_url",""),"similarity":max(0.0,1.0-float(distance))})
    return sorted(found,key=lambda item:item["similarity"],reverse=True)[:limit]

def status():
    available=_load_stack()
    return {"available":available,"collections":list(_collections),"embedding_backend":EMBEDDING_BACKEND}
