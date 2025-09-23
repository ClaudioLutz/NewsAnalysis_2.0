# prefilter/embedding_utils.py
from __future__ import annotations
import hashlib, json, os, time
from typing import Iterable, List, Tuple
import numpy as np
from openai import OpenAI

from pathlib import Path
CACHE_DIR = str(Path(__file__).resolve().parent.parent / "outputs" / "cache")

def _hash_key(text: str, model: str, dims: int) -> str:
    h = hashlib.sha1()
    h.update(model.encode())
    h.update(b"|")
    h.update(str(dims).encode())
    h.update(b"|")
    h.update(text.encode("utf-8", errors="ignore"))
    return h.hexdigest()

def _cache_path(key: str) -> str:
    sub = Path(CACHE_DIR) / key[:2]
    sub.mkdir(parents=True, exist_ok=True)
    return str(sub / f"{key}.npy")

def embed_texts(
    texts: List[str],
    model: str = "text-embedding-3-small",
    dims: int = 512,
    batch_size: int = 512,
    sleep_on_rate_limit: float = 2.0,
) -> np.ndarray:
    """
    Returns L2-normalized embeddings (shape: [len(texts), dims]).
    V3 embeddings are unit-normalized according to OpenAI; we still re-normalize defensively.
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    client = OpenAI()

    # Prepare cache masks
    keys = [_hash_key(t or "", model, dims) for t in texts]
    out = np.zeros((len(texts), dims), dtype=np.float32)
    missing_ix = []
    missing_texts = []

    for i, (t, k) in enumerate(zip(texts, keys)):
        p = _cache_path(k)
        if Path(p).exists():
            out[i] = np.load(p)
        else:
            missing_ix.append(i)
            missing_texts.append(t or "")

    # Fetch missing in batches
    for start in range(0, len(missing_texts), batch_size):
        chunk = missing_texts[start : start + batch_size]
        done = False
        while not done:
            try:
                resp = client.embeddings.create(
                    model=model,
                    input=chunk,
                    dimensions=dims,  # v3 supports shortening via `dimensions`
                )
                vecs = np.array([d.embedding for d in resp.data], dtype=np.float32)
                # defensive re-normalization
                norms = np.linalg.norm(vecs, axis=1, keepdims=True)
                vecs = vecs / np.clip(norms, 1e-12, None)

                for j, v in enumerate(vecs):
                    idx = missing_ix[start + j]
                    out[idx] = v
                    np.save(_cache_path(keys[idx]), v)
                done = True
            except Exception as e:
                # crude backoff; rely on cache across retries
                time.sleep(sleep_on_rate_limit)
                if "rate" not in str(e).lower():
                    raise
    # final safety normalization
    norms = np.linalg.norm(out, axis=1, keepdims=True)
    out = out / np.clip(norms, 1e-12, None)
    return out

def dot_max_against_seeds(title_vecs: np.ndarray, seed_vecs: np.ndarray) -> np.ndarray:
    """
    Because vectors are L2-normalized, cosine ≡ dot product.
    Score each title by max(dot(title, seed_i)).
    """
    sims = title_vecs @ seed_vecs.T
    return sims.max(axis=1)
