# prefilter/tune_prefilter.py
from __future__ import annotations
import argparse, json, os
import numpy as np
import pandas as pd
from embedding_utils import embed_texts

DEFAULT_MODEL = "text-embedding-3-small"
DEFAULT_DIMS  = 512

def _centroid(vecs: np.ndarray) -> np.ndarray:
    if vecs.size == 0:
        return None
    c = vecs.mean(axis=0, keepdims=True)
    n = np.linalg.norm(c, axis=1, keepdims=True)
    return (c / np.clip(n, 1e-12, None)).astype(np.float32)[0]

def _contrast_goal(pos: np.ndarray, neg: np.ndarray, alpha: float) -> np.ndarray:
    cp = _centroid(pos) if pos is not None else None
    cn = _centroid(neg) if neg is not None else None
    if cp is None and cn is None:
        raise ValueError("Need at least some positives or negatives.")
    v = np.zeros_like(pos[0] if pos is not None else neg[0])
    if cp is not None: v += cp
    if cn is not None: v -= alpha * cn
    v = v / np.clip(np.linalg.norm(v), 1e-12, None)
    return v.astype(np.float32)

def _score_against_vector(title_vecs: np.ndarray, goal_vec: np.ndarray) -> np.ndarray:
    return title_vecs @ goal_vec  # cosine via dot (unit vecs)

def _auto_cutoff_supervised(scores: np.ndarray, labels: np.ndarray, optimize: str, target_precision: float):
    # grid search cutoff
    cuts = np.linspace(0.05, 0.6, 56)  # 0.05..0.60 step 0.01
    best = {"cutoff": 0.25, "f1": -1.0, "precision": 0, "recall": 0}
    for c in cuts:
        keep = scores >= c
        tp = int(((labels == 1) & keep).sum())
        fp = int(((labels == 0) & keep).sum())
        fn = int(((labels == 1) & ~keep).sum())
        prec = tp / (tp + fp + 1e-9)
        rec = tp / (tp + fn + 1e-9)
        f1  = 2 * prec * rec / (prec + rec + 1e-9)
        if optimize == "precision_at_target":
            # choose smallest cutoff that achieves target precision; break ties by higher recall
            if prec >= target_precision:
                if best["precision"] < target_precision or rec > best["recall"]:
                    best = {"cutoff": float(c), "f1": float(f1), "precision": float(prec), "recall": float(rec)}
        else:
            if f1 > best["f1"]:
                best = {"cutoff": float(c), "f1": float(f1), "precision": float(prec), "recall": float(rec)}
    return best

def _auto_cutoff_unsupervised(scores: np.ndarray, keep_rate: float | None, q: float) -> float:
    if keep_rate is not None:
        # choose cutoff that keeps approx keep_rate fraction
        k = max(1, int(round(len(scores) * keep_rate)))
        return float(np.sort(scores)[::-1][k-1])
    # else choose high quantile (e.g., 0.90)
    return float(np.quantile(scores, q))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True, help="Path to last_week.csv with columns: id,title,topic[,label]")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--dims", type=int, default=DEFAULT_DIMS)
    ap.add_argument("--alpha", type=float, default=0.7, help="contrast weight for negatives")
    ap.add_argument("--optimize", choices=["f1", "precision_at_target"], default="f1")
    ap.add_argument("--target_precision", type=float, default=0.9)
    ap.add_argument("--unsup_keep_rate", type=float, default=None, help="If set, keep this fraction in unsupervised mode")
    ap.add_argument("--unsup_quantile", type=float, default=0.90, help="Else use this quantile for cutoff")
    ap.add_argument("--seed", action="append", help="Add a goal seed sentence; may repeat", default=[])
    ap.add_argument("--seeds_file", help="Text file with one seed per line")
    from pathlib import Path
    _ROOT = Path(__file__).resolve().parents[1]
    ap.add_argument("--out_model", default=str(_ROOT / "outputs" / "prefilter_model.json"))
    ap.add_argument("--out_scores", default=str(_ROOT / "outputs" / "debug_scores.csv"))
    args = ap.parse_args()

    df = pd.read_csv(args.csv)
    need_label = "label" in df.columns
    if not need_label and not (args.seed or args.seeds_file):
        raise SystemExit("Unsupervised mode requires --seed or --seeds_file")

    # Gather seeds (only for unsupervised mode)
    seeds = list(args.seed or [])
    if args.seeds_file and not need_label:  # Only load seeds if no labels available
        with open(args.seeds_file, "r", encoding="utf-8") as fh:
            seeds += [ln.strip() for ln in fh if ln.strip()]
    seeds = list(dict.fromkeys(seeds))  # dedupe
    
    # Force supervised mode if labels are available
    if need_label:
        seeds = []  # Clear seeds to ensure supervised training

    topics = sorted(df["topic"].unique())
    model_spec = {
        "model": args.model,
        "dims": args.dims,
        "alpha": args.alpha,
        "topics": {}
    }
    debug_rows = []

    for topic in topics:
        sub = df[df["topic"] == topic].copy()
        titles = sub["title"].fillna("").tolist()
        ids    = sub["id"].tolist()
        title_vecs = embed_texts(titles, model=args.model, dims=args.dims)

        # mode: supervised
        if "label" in sub.columns:
            labels = sub["label"].astype(int).values
            pos_vecs = title_vecs[labels == 1]
            neg_vecs = title_vecs[labels == 0] if (labels == 0).any() else np.zeros((0, args.dims), np.float32)

            # if no labeled negatives, derive weak negatives as bottom-quantile
            if neg_vecs.shape[0] == 0:
                # score against positive centroid to bootstrap weak negatives
                boot_goal = _centroid(pos_vecs)
                boot_scores = title_vecs @ boot_goal
                q = np.quantile(boot_scores, 0.20)
                neg_vecs = title_vecs[boot_scores <= q]

            goal_vec = _contrast_goal(pos_vecs, neg_vecs, alpha=args.alpha)
            scores   = _score_against_vector(title_vecs, goal_vec)

            best = _auto_cutoff_supervised(scores, labels, args.optimize, args.target_precision)
            cutoff = float(best["cutoff"])
            metrics = {"precision": best["precision"], "recall": best["recall"], "f1": best["f1"]}

        else:
            # mode: unsupervised — build seeds, then mine soft P/N
            seed_vecs = embed_texts(seeds, model=args.model, dims=args.dims)
            seed_scores = title_vecs @ seed_vecs.T
            max_scores  = seed_scores.max(axis=1)

            # select top 15% as pseudo-positives, bottom 30% as pseudo-negatives
            p_cut = np.quantile(max_scores, 0.85)
            n_cut = np.quantile(max_scores, 0.30)
            pos_vecs = title_vecs[max_scores >= p_cut]
            neg_vecs = title_vecs[max_scores <= n_cut]

            goal_vec = _contrast_goal(pos_vecs, neg_vecs, alpha=args.alpha)
            scores   = _score_against_vector(title_vecs, goal_vec)

            cutoff = _auto_cutoff_unsupervised(scores, args.unsup_keep_rate, args.unsup_quantile)
            metrics = {"precision": None, "recall": None, "f1": None}

        # stash debug
        for i, s in zip(ids, scores):
            debug_rows.append({"topic": topic, "id": i, "score": float(s)})

        model_spec["topics"][topic] = {
            "cutoff": cutoff,
            "goal_vec": goal_vec.tolist(),
            "seeds": seeds if not need_label else None,
            "metrics": metrics
        }

    Path(args.out_model).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out_model, "w", encoding="utf-8") as fh:
        json.dump(model_spec, fh, ensure_ascii=False, indent=2)

    pd.DataFrame(debug_rows).to_csv(args.out_scores, index=False)
    print(f"Saved model -> {args.out_model}")
    print(f"Saved debug scores -> {args.out_scores}")

if __name__ == "__main__":
    main()
