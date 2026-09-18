# AROL Customer Platform - Project Q2

**Multi-agent AI framework for industrial fleet management and autonomous troubleshooting.**
System and Device Programming, A.Y. 2025-2026, Politecnico di Torino / AROL S.p.A.

A plant operator scans the QR code applied to a machine, lands on the page of that
machine and asks a chatbot about it. The chatbot is an orchestrator: it routes each
question to one of three specialized agents, which answer only through tools over the
fleet dataset. The agents never answer from memory, and access is restricted both by
company and by the visibility level of the user.

| Agent | Answers about | Reaches the data through |
|---|---|---|
| `manuals` | machine identity, configuration, anything written in the manual | TF-IDF retrieval over the manual of that specific machine |
| `diagnostics` | telemetry, alarms, maintenance tickets, troubleshooting | aggregating SQL queries |
| `commercial` | quotations, revisions, orders | aggregating SQL queries |

## How one question is answered

1. the message is stored in `Messages`;
2. **routing** - one model call answers with a single word: `manuals`, `diagnostics`,
   `commercial` or `general`;
3. **access check** - if the user's visibility does not cover that agent's data domain,
   the agent never runs and an explicit refusal is returned;
4. **agent loop** - system prompt, the last six messages and the question, sent with that
   agent's tool schemas; tool calls are executed and their JSON appended, at most four rounds;
5. the answer comes back with the manual pages it cited, which the interface turns into
   links that open the PDF at that page.

```
React (Vite)  ->  FastAPI  ->  orchestrator  ->  agents  ->  12 tools  ->  SQLite
                                                                       -> TF-IDF index
```

`backend/llm.py` is the only file that knows about the model provider; any
OpenAI-compatible endpoint with tool calling works.

## Running it

Needs Python 3.11+, Node 18+, a free API key for an OpenAI-compatible model, and the
course dataset, which is **not in this repository**: copy it into the project root as
`Project-Q2-DataBase/`.

```bash
python3.11 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env                      # put the key in LLM_API_KEY
cd backend && python load_data.py         # workbook  -> data/arol.db
python build_index.py                     # manuals   -> data/manual_index.pkl
cd ../frontend && npm install
```

Then, in two terminals:

```bash
cd backend && ../.venv/bin/uvicorn main:app --reload    # port 8000
cd frontend && npm run dev                              # port 5173
```

Sign in at <http://localhost:5173> with a dataset address and the demo password
`arol2026`. `elena.fabbri@valgrande.example` sees everything,
`matteo.bonetti@valgrande.example` is a technician, `davide.ranieri@valgrande.example`
is commercial. A machine page is `/machines/15610`, which is what its QR code encodes.

`README.txt` documents every parameter; `DOCUMENTATION.md` explains why each decision
was taken.

## Evaluation

Three scripts in `evaluation/`, all run by hand.

**Correctness.** Fourteen questions with known answers, covering the three agents and the
refusals. All fourteen were answered correctly, and after a fix to the router prompt all
fourteen reached the expected agent in six repetitions each.

![Routing stability](docs/figures/routing_stability.png)

**Retrieval.** TF-IDF against `all-MiniLM-L6-v2` embeddings on twelve manual questions
with page-level ground truth, and then both retrievers unchanged on the public
BEIR/SciFact benchmark. TF-IDF wins when the question uses the manual's own wording,
embeddings win when it uses an operator's, and on SciFact the ordering reverses - which
is the point: the better retriever depends on the corpus and on how the question is
phrased. Our SciFact number for the embeddings, 0.645, is exactly the published figure,
so the harness is verified.

![Retrieval by wording](docs/figures/retrieval_by_wording.png)
![Public benchmark](docs/figures/public_benchmark.png)

**Behaviour.** `functional_checks.py` runs 59 checks over the HTTP API, the twelve tools
and the access model without calling the model, so it is free and takes two seconds.

## Notes

The dataset and the eight manuals are AROL teaching copies provided by the course and are
not redistributed here. `.env` is gitignored; `.env.example` carries a placeholder.

Emir Turkmen (s353921) and Misra Nur Ozdemir (s358966).
