"""Compare the TF-IDF retrieval of the platform with an embedding retriever.

Part of the evaluation, not of the platform: the backend never imports it and its
dependency (sentence-transformers) is not in requirements.txt. Install it only to
repeat this measurement:

    ../.venv/bin/pip install sentence-transformers
    ../.venv/bin/python retrieval_comparison.py

Both retrievers search the same chunks (one manual page each) and both filter by
serial number before ranking, like tools.search_manual does. The ground truth
below is the set of pages that really answer each question; we found them by
reading the manuals, not by trusting either retriever.

Half of the questions use the wording of the manual, half are paraphrases an
operator would use. That split is the point: word matching should do well on the
first half and badly on the second.
"""

import json
import pickle
import time

import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

import sys
sys.path.insert(0, "../backend")
from config import DATA_DIR, INDEX_PATH  # noqa: E402

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDINGS_PATH = DATA_DIR / "manual_embeddings.npy"
RESULTS_PATH = DATA_DIR / "retrieval_comparison.json"
TOP_K = 3

# question, serial number, pages that answer it, wording style
QUESTIONS = [
    ("Which safety procedures must I follow before maintenance on this machine?",
     "15610", {30, 33}, "manual wording"),
    ("What must I do before opening the machine so that it cannot start while I work inside?",
     "15610", {30, 33}, "operator wording"),
    ("How is the tightening torque of the closure head adjusted?",
     "15610", {89}, "manual wording"),
    # page 89 gives the adjustment, page 153 is the fault table entry
    # ("the cap is not totally screwed" -> "increase the head tightening torque")
    ("The caps come out too loose, which adjustment should I check?",
     "15610", {89, 153}, "operator wording"),
    ("What has to be done every 500 working hours?",
     "15610", {98}, "manual wording"),
    ("How many closure heads does this machine have and what is its nominal production rate?",
     "15610", {1, 21}, "manual wording"),
    ("How do I check the compressed air supply and look for leaks?",
     "15610", {97, 98}, "operator wording"),
    ("What happens when an emergency mushroom button is pressed?",
     "15610", {31}, "manual wording"),
    ("How often should the outside of the machine be washed?",
     "15610", {53}, "operator wording"),
    ("Which grease may I use on parts that can touch the product?",
     "15610", {129, 130, 131}, "operator wording"),
    ("Where is the list of faults and their possible remedies?",
     "15610", {150}, "manual wording"),
    ("How many heads does machine 17203 have and how fast does it run?",
     "17203", {1, 18}, "operator wording"),
]


def load_index():
    with open(INDEX_PATH, "rb") as f:
        return pickle.load(f)


def embed_chunks(index):
    """Embed every manual page once and cache the result on disk."""
    model = SentenceTransformer(EMBEDDING_MODEL)
    if EMBEDDINGS_PATH.exists():
        vectors = np.load(EMBEDDINGS_PATH)
        if len(vectors) == len(index["chunks"]):
            print(f"Cached embeddings: {vectors.shape}")
            return model, vectors
    print(f"Embedding {len(index['chunks'])} pages with {EMBEDDING_MODEL} ...")
    started = time.time()
    vectors = model.encode([c["text"] for c in index["chunks"]],
                           batch_size=32, show_progress_bar=False)
    np.save(EMBEDDINGS_PATH, vectors)
    print(f"  done in {time.time() - started:.0f} s, matrix {vectors.shape}")
    return model, vectors


def top_pages(scores, positions, index, k=TOP_K):
    best = sorted(range(len(positions)), key=lambda i: scores[i], reverse=True)[:k]
    return [index["chunks"][positions[i]]["page"] for i in best]


def evaluate(index, model, embeddings):
    rows = []
    for question, serial, relevant, style in QUESTIONS:
        positions = [i for i, c in enumerate(index["chunks"]) if c["serialNumber"] == serial]

        started = time.time()
        tfidf_scores = cosine_similarity(
            index["vectorizer"].transform([question]), index["matrix"][positions])[0]
        tfidf_pages = top_pages(tfidf_scores, positions, index)
        tfidf_ms = (time.time() - started) * 1000

        started = time.time()
        query_vector = model.encode([question])
        embed_scores = cosine_similarity(query_vector, embeddings[positions])[0]
        embed_pages = top_pages(embed_scores, positions, index)
        embed_ms = (time.time() - started) * 1000

        rows.append({
            "question": question,
            "serialNumber": serial,
            "style": style,
            "relevantPages": sorted(relevant),
            "tfidf": {"pages": tfidf_pages, "ms": round(tfidf_ms, 1)},
            "embedding": {"pages": embed_pages, "ms": round(embed_ms, 1)},
        })
    return rows


def score(pages, relevant):
    """hit@1, hit@3 and the reciprocal rank of the first relevant page."""
    hit1 = pages[0] in relevant
    hit3 = any(p in relevant for p in pages)
    rank = next((i + 1 for i, p in enumerate(pages) if p in relevant), None)
    return hit1, hit3, (1 / rank if rank else 0.0)


def report(rows):
    print(f"\n{'question':<62} {'style':<16} {'TF-IDF top 3':<18} {'embedding top 3'}")
    print("-" * 120)
    summary = {}
    for row in rows:
        line = f"{row['question'][:60]:<62} {row['style']:<16} "
        for method in ("tfidf", "embedding"):
            hit1, hit3, rr = score(row[method]["pages"], set(row["relevantPages"]))
            row[method].update({"hit1": hit1, "hit3": hit3, "reciprocalRank": round(rr, 3)})
            mark = "+" if hit3 else "-"
            line += f"{str(row[method]['pages']) + ' ' + mark:<18} "
        print(line)

    for method in ("tfidf", "embedding"):
        n = len(rows)
        summary[method] = {
            "hit@1": round(sum(r[method]["hit1"] for r in rows) / n, 3),
            "hit@3": round(sum(r[method]["hit3"] for r in rows) / n, 3),
            "MRR": round(sum(r[method]["reciprocalRank"] for r in rows) / n, 3),
            "msPerQuery": round(sum(r[method]["ms"] for r in rows) / n, 1),
        }
        for style in ("manual wording", "operator wording"):
            subset = [r for r in rows if r["style"] == style]
            summary[method][f"hit@3 ({style})"] = round(
                sum(r[method]["hit3"] for r in subset) / len(subset), 3)

    print(f"\n{'metric':<26} {'TF-IDF':>10} {'embedding':>12}")
    print("-" * 50)
    for metric in ("hit@1", "hit@3", "MRR", "hit@3 (manual wording)",
                   "hit@3 (operator wording)", "msPerQuery"):
        print(f"{metric:<26} {summary['tfidf'][metric]:>10} {summary['embedding'][metric]:>12}")
    return summary


def main():
    index = load_index()
    model, embeddings = embed_chunks(index)
    rows = evaluate(index, model, embeddings)
    summary = report(rows)
    with open(RESULTS_PATH, "w") as f:
        json.dump({"questions": rows, "summary": summary,
                   "embeddingModel": EMBEDDING_MODEL, "topK": TOP_K}, f, indent=2)
    print(f"\nResults written to {RESULTS_PATH}")


if __name__ == "__main__":
    main()
