"""Draw the figures used in DOCUMENTATION.md section 9.

Evaluation only, like retrieval_comparison.py: matplotlib is not a dependency of
the platform and is not in requirements.txt.

    ../.venv/bin/pip install matplotlib
    ../.venv/bin/python make_plots.py

The retrieval numbers are read from the JSON written by retrieval_comparison.py
and by public_benchmark.py.
The routing numbers are the measurement described in DOCUMENTATION.md section 9:
each question was routed six times, before and after the fix to the router prompt.
"""

import json
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, "../backend")
from config import DATA_DIR, PROJECT_ROOT  # noqa: E402

FIGURES = PROJECT_ROOT / "docs" / "figures"
BLUE, AMBER, GREY = "#1f6fb2", "#e09a2b", "#8a97a3"

# Correct routings out of six repetitions (section 9, "Routing stability").
# Q1 has five valid runs before the fix: one call hit the rate limit.
ROUTING = [
    ("Q1 safety", 5, 6, 5),
    ("Q2 heads & rate", 1, 6, 6),
    ("Q3 alarms", 6, 6, 6),
    ("Q8 order cost", 6, 6, 6),
    ("Q10 fleet list", 3, 6, 6),
    ("Q11 refusal", 6, 6, 6),
]


def style(ax, title, ylabel):
    ax.set_title(title, fontsize=11, pad=10)
    ax.set_ylabel(ylabel, fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color="#dfe5ea", linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(labelsize=8.5)


def bars_with_values(ax, xs, values, color, label, fmt="{:.2f}"):
    rects = ax.bar(xs, values, width=0.38, color=color, label=label)
    for rect, value in zip(rects, values):
        ax.text(rect.get_x() + rect.get_width() / 2, value + 0.02, fmt.format(value),
                ha="center", va="bottom", fontsize=8)


def retrieval_accuracy(summary):
    metrics = ["hit@1", "hit@3", "MRR"]
    fig, ax = plt.subplots(figsize=(6.2, 3.4))
    xs = range(len(metrics))
    bars_with_values(ax, [x - 0.2 for x in xs], [summary["tfidf"][m] for m in metrics],
                     BLUE, "TF-IDF (in the platform)")
    bars_with_values(ax, [x + 0.2 for x in xs], [summary["embedding"][m] for m in metrics],
                     AMBER, "all-MiniLM-L6-v2 embeddings")
    ax.set_xticks(list(xs), metrics)
    ax.set_ylim(0, 1.05)
    style(ax, "Manual retrieval: 12 questions, page-level ground truth", "score")
    ax.legend(frameon=False, fontsize=8.5, loc="upper right")
    fig.tight_layout()
    fig.savefig(FIGURES / "retrieval_accuracy.png", dpi=200)
    plt.close(fig)


def retrieval_by_wording(summary):
    groups = ["manual wording\n(6 questions)", "operator wording\n(6 questions)"]
    keys = ["hit@3 (manual wording)", "hit@3 (operator wording)"]
    fig, ax = plt.subplots(figsize=(6.2, 3.4))
    xs = range(len(groups))
    bars_with_values(ax, [x - 0.2 for x in xs], [summary["tfidf"][k] for k in keys],
                     BLUE, "TF-IDF")
    bars_with_values(ax, [x + 0.2 for x in xs], [summary["embedding"][k] for k in keys],
                     AMBER, "embeddings")
    ax.set_xticks(list(xs), groups)
    # headroom so the legend never sits on a value label
    ax.set_ylim(0, 1.28)
    ax.set_yticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
    style(ax, "hit@3 by question wording", "hit@3")
    ax.legend(frameon=False, fontsize=8.5, ncol=2, loc="upper center")
    fig.tight_layout()
    fig.savefig(FIGURES / "retrieval_by_wording.png", dpi=200)
    plt.close(fig)


def retrieval_latency(summary):
    fig, ax = plt.subplots(figsize=(4.2, 3.2))
    values = [summary["tfidf"]["msPerQuery"], summary["embedding"]["msPerQuery"]]
    rects = ax.bar(["TF-IDF", "embeddings"], values, width=0.5, color=[BLUE, AMBER])
    for rect, value in zip(rects, values):
        ax.text(rect.get_x() + rect.get_width() / 2, value, f"{value:.1f} ms",
                ha="center", va="bottom", fontsize=9)
    ax.set_ylim(0, max(values) * 1.25)
    style(ax, "Cost of one retrieval query", "milliseconds")
    fig.tight_layout()
    fig.savefig(FIGURES / "retrieval_latency.png", dpi=200)
    plt.close(fig)


def public_benchmark(summary):
    """The same two retrievers on SciFact (BEIR), section 9."""
    metrics = ["hit@1", "hit@3", "MRR@10", "nDCG@10"]
    fig, ax = plt.subplots(figsize=(6.2, 3.4))
    xs = range(len(metrics))
    bars_with_values(ax, [x - 0.2 for x in xs], [summary["tfidf"][m] for m in metrics],
                     BLUE, "TF-IDF (in the platform)")
    bars_with_values(ax, [x + 0.2 for x in xs], [summary["embedding"][m] for m in metrics],
                     AMBER, "all-MiniLM-L6-v2 embeddings")
    ax.set_xticks(list(xs), metrics)
    ax.set_ylim(0, 1.05)
    style(ax, "Public benchmark: SciFact (BEIR), 300 queries over 5183 documents", "score")
    ax.legend(frameon=False, fontsize=8.5, loc="upper right")
    fig.tight_layout()
    fig.savefig(FIGURES / "public_benchmark.png", dpi=200)
    plt.close(fig)


def routing_stability():
    labels = [row[0] for row in ROUTING]
    before = [row[1] for row in ROUTING]
    after = [row[2] for row in ROUTING]
    runs = [row[3] for row in ROUTING]
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    xs = range(len(labels))
    ax.bar([x - 0.2 for x in xs], before, width=0.38, color=GREY, label="before the fix")
    ax.bar([x + 0.2 for x in xs], after, width=0.38, color=AMBER, label="after the fix")
    for x, (b, a, r) in enumerate(zip(before, after, runs)):
        ax.text(x - 0.2, b + 0.08, f"{b}/{r}", ha="center", fontsize=8)
        ax.text(x + 0.2, a + 0.08, f"{a}/6", ha="center", fontsize=8)
    ax.set_xticks(list(xs), labels, rotation=12, ha="right")
    # headroom above the tallest bar (6) so the legend never covers a bar
    ax.set_ylim(0, 8)
    ax.set_yticks(range(0, 7, 2))
    style(ax, "Routing: correct handler over six repetitions", "correct routings")
    ax.legend(frameon=False, fontsize=8.5, ncol=2, loc="upper center")
    fig.tight_layout()
    fig.savefig(FIGURES / "routing_stability.png", dpi=200)
    plt.close(fig)


def main():
    FIGURES.mkdir(parents=True, exist_ok=True)
    with open(DATA_DIR / "retrieval_comparison.json") as f:
        summary = json.load(f)["summary"]
    retrieval_accuracy(summary)
    retrieval_by_wording(summary)
    retrieval_latency(summary)
    with open(DATA_DIR / "public_benchmark.json") as f:
        public_benchmark(json.load(f)["summary"])
    routing_stability()
    for path in sorted(FIGURES.glob("*.png")):
        print("wrote", path.relative_to(PROJECT_ROOT))


if __name__ == "__main__":
    main()
