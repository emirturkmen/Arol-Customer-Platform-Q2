"""Build the index the Manuals agent searches (RAG).

One PDF page = one chunk, indexed with TF-IDF. TF-IDF needs no extra service and
matches technical wording well ("LOW AIR PRESSURE", "closure head").

Run once before starting the backend:  python backend/build_index.py
"""

import pickle
import re

import pypdf
from sklearn.feature_extraction.text import TfidfVectorizer

from config import DATA_DIR, INDEX_PATH, MANUALS_DIR

# Repeated on every page. Removing it keeps the TF-IDF scores meaningful.
BOILERPLATE = [
    "THIS MANUAL IS PROPERTY OF AROL S.p.A.. ANY REPRODUCTION OR MODIFICATION, EVEN IN PART, IS PROHIBITED.",
    "AROL S.p.A. - teaching copy, Politecnico di Torino, System and Device Programming. Do not redistribute.",
]


def clean(text):
    for line in BOILERPLATE:
        text = text.replace(line, " ")
    return re.sub(r"\s+", " ", text).strip()


def read_manual(path):
    """Return a list of (page_number, text) for one manual."""
    pages = []
    reader = pypdf.PdfReader(path)
    for number, page in enumerate(reader.pages, start=1):
        text = clean(page.extract_text() or "")
        if len(text) > 100:  # skip title pages, figure-only pages, etc.
            pages.append((number, text))
    return pages


def main():
    DATA_DIR.mkdir(exist_ok=True)
    chunks = []
    for path in sorted(MANUALS_DIR.glob("*_manual_EN.pdf")):
        serial = path.name.split("_")[0]
        pages = read_manual(path)
        for number, text in pages:
            chunks.append({"serialNumber": serial, "page": number, "text": text})
        print(f"{path.name}: {len(pages)} indexed pages")

    vectorizer = TfidfVectorizer(stop_words="english", sublinear_tf=True)
    matrix = vectorizer.fit_transform(c["text"] for c in chunks)

    with open(INDEX_PATH, "wb") as f:
        pickle.dump({"chunks": chunks, "vectorizer": vectorizer, "matrix": matrix}, f)
    print(f"Indexed {len(chunks)} pages into {INDEX_PATH}")


if __name__ == "__main__":
    main()
