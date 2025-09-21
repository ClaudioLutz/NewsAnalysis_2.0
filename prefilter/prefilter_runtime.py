# prefilter/prefilter_runtime.py
from __future__ import annotations
import json, os
from typing import Dict, List, Tuple
import numpy as np
from prefilter.embedding_utils import embed_texts

def load_prefilter_model(path: str) -> Dict:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)

def prefilter_titles(
    articles: List[Dict],              # each: {"id":..., "title":..., "topic":...}
    model_path: str = os.path.join("outputs", "prefilter_model.json"),
) -> Tuple[List[Dict], List[Tuple[str, float]]]:
    spec = load_prefilter_model(model_path)
    model = spec["model"]; dims = int(spec["dims"])

    # group by topic
    by_topic: Dict[str, List[int]] = {}
    titles = []
    for idx, a in enumerate(articles):
        t = a.get("topic") or "default"
        by_topic.setdefault(t, []).append(idx)
        titles.append(a.get("title") or "")

    title_vecs = embed_texts(titles, model=model, dims=dims)
    keep, dbg = [], []

    for topic, idxs in by_topic.items():
        topic_cfg = spec["topics"].get(topic)
        if not topic_cfg:
            # fall back: pass-through if topic wasn't tuned yet
            for i in idxs: keep.append(articles[i]); dbg.append((articles[i]["id"], 1.0))
            continue

        goal_vec = np.array(topic_cfg["goal_vec"], dtype=np.float32)
        cutoff   = float(topic_cfg["cutoff"])
        scores   = (title_vecs[idxs] @ goal_vec)

        order = np.argsort(-scores)
        for j in order:
            sc = float(scores[j])
            if sc >= cutoff:
                keep.append(articles[idxs[j]])
                dbg.append((articles[idxs[j]]["id"], sc))

    return keep, dbg
