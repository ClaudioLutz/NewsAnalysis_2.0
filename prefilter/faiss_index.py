# prefilter/faiss_index.py
import faiss, numpy as np

def build_ip_index(vecs: np.ndarray, m: int = 32) -> faiss.Index:
    faiss.normalize_L2(vecs)  # cosine via IP
    index = faiss.IndexHNSWFlat(vecs.shape[1], m, faiss.METRIC_INNER_PRODUCT)
    index.hnsw.efConstruction = 200
    index.add(vecs)
    return index

def search_ip(index: faiss.Index, queries: np.ndarray, k: int = 200):
    faiss.normalize_L2(queries)
    scores, ids = index.search(queries, k)
    return scores, ids
