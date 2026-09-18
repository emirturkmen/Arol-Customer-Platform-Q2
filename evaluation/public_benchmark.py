"""The retrieval step of the platform, run on a public benchmark.

The course rules ask for results on public benchmarks and not only on our own
data. retrieval_comparison.py measures the two retrievers on the AROL manuals;
this script measures the same two, without changing them, on SciFact from the
BEIR collection: 5,183 scientific abstracts and 300 test claims with public
relevance judgements.

We picked SciFact because it is the public set closest to our own corpus: short
factual questions asked against technical documents full of exact terms.

Like the other evaluation scripts it is not part of the platform, and its
dependency is not in requirements.txt:

    ../.venv/bin/pip install sentence-transformers
    ../.venv/bin/python public_benchmark.py

The dataset (about 3 MB) is downloaded once into data/beir/ and kept there.
"""

import io
import json
import sys
import time
import urllib.request
import zipfile
from collections import defaultdict

import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

sys.path.insert(0, "../backend")
from config import DATA_DIR  # noqa: E402

URL = "https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets/scifact.zip"
BEIR_DIR = DATA_DIR / "beir"
SCIFACT = BEIR_DIR / "scifact"
EMBEDDINGS_PATH = DATA_DIR / "scifact_embeddings.npy"
RESULTS_PATH = DATA_DIR / "public_benchmark.json"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
TOP_K = 10


def download():
    if SCIFACT.exists():
        return
    BEIR_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {URL} ...")
    with urllib.request.urlopen(URL, timeout=120) as response:
        archive = zipfile.ZipFile(io.BytesIO(response.read()))
    archive.extractall(BEIR_DIR)
    print(f"  extracted to {SCIFACT}")


def load():
    """corpus texts, their ids, the test queries and their relevant documents."""
    documents, document_ids = [], []
    with open(SCIFACT / "corpus.jsonl") as f:
        for line in f:
            row = json.loads(line)
            document_ids.append(row["_id"])
            documents.append((row.get("title", "") + " " + row.get("text", "")).strip())

    relevant = defaultdict(set)
    with open(SCIFACT / "qrels" / "test.tsv") as f:
        next(f)                                   # header
        for line in f:
            query_id, document_id, score = line.split()
            if int(score) > 0:
                relevant[query_id].add(document_id)

    queries = []
    with open(SCIFACT / "queries.jsonl") as f:
        for line in f:
            row = json.loads(line)
            if row["_id"] in relevant:
                queries.append((row["_id"], row["text"]))
    return documents, document_ids, queries, relevant


def embed(documents):
    model = SentenceTransformer(EMBEDDING_MODEL)
    if EMBEDDINGS_PATH.exists():
        vectors = np.load(EMBEDDINGS_PATH)
        if len(vectors) == len(documents):
            print(f"Cached embeddings: {vectors.shape}")
            return model, vectors
    print(f"Embedding {len(documents)} documents with {EMBEDDING_MODEL} ...")
    started = time.time()
    vectors = model.encode(documents, batch_size=64, show_progress_bar=False)
    np.save(EMBEDDINGS_PATH, vectors)
    print(f"  done in {time.time() - started:.0f} s, matrix {vectors.shape}")
    return model, vectors


def score(ranked, relevant):
    """hit@1, hit@3, reciprocal rank and nDCG@10 for one query."""
    hit1 = ranked[0] in relevant
    hit3 = any(d in relevant for d in ranked[:3])
    rank = next((i + 1 for i, d in enumerate(ranked) if d in relevant), None)
    gains = [1 / np.log2(i + 2) for i, d in enumerate(ranked[:10]) if d in relevant]
    ideal = sum(1 / np.log2(i + 2) for i in range(min(len(relevant), 10)))
    return hit1, hit3, (1 / rank if rank else 0.0), (sum(gains) / ideal if ideal else 0.0)


def evaluate(name, rank_query, queries, document_ids, relevant):
    totals = np.zeros(4)
    started = time.time()
    for query_id, text in queries:
        ranked = [document_ids[i] for i in rank_query(text)]
        totals += score(ranked, relevant[query_id])
    milliseconds = (time.time() - started) * 1000 / len(queries)
    hit1, hit3, mrr, ndcg = totals / len(queries)
    print(f"{name:<12} hit@1 {hit1:.3f}   hit@3 {hit3:.3f}   MRR@10 {mrr:.3f}   "
          f"nDCG@10 {ndcg:.3f}   {milliseconds:.1f} ms/query")
    return {"hit@1": round(hit1, 3), "hit@3": round(hit3, 3), "MRR@10": round(mrr, 3),
            "nDCG@10": round(ndcg, 3), "msPerQuery": round(milliseconds, 1)}


def main():
    download()
    documents, document_ids, queries, relevant = load()
    print(f"SciFact: {len(documents)} documents, {len(queries)} test queries")

    # The same vectorizer settings as backend/build_index.py.
    vectorizer = TfidfVectorizer(stop_words="english", sublinear_tf=True)
    matrix = vectorizer.fit_transform(documents)
    model, embeddings = embed(documents)

    def tfidf_rank(text):
        scores = cosine_similarity(vectorizer.transform([text]), matrix)[0]
        return np.argsort(scores)[::-1][:TOP_K]

    def embedding_rank(text):
        scores = cosine_similarity(model.encode([text]), embeddings)[0]
        return np.argsort(scores)[::-1][:TOP_K]

    print()
    summary = {
        "tfidf": evaluate("TF-IDF", tfidf_rank, queries, document_ids, relevant),
        "embedding": evaluate("embeddings", embedding_rank, queries, document_ids, relevant),
    }
    with open(RESULTS_PATH, "w") as f:
        json.dump({"dataset": "BEIR / SciFact (test split)", "documents": len(documents),
                   "queries": len(queries), "embeddingModel": EMBEDDING_MODEL,
                   "topK": TOP_K, "summary": summary}, f, indent=2)
    print(f"\nResults written to {RESULTS_PATH}")


if __name__ == "__main__":
    main()
