AROL CUSTOMER PLATFORM - PROJECT Q2
Multi-Agent AI Framework for Industrial Fleet Management and Autonomous
Troubleshooting
System and Device Programming, A.Y. 2025-2026, Politecnico di Torino / AROL S.p.A.


1. WHAT THIS IS
---------------

A web platform where a plant operator scans the QR code applied to a machine,
lands on the page of that machine (data + use-and-maintenance manual) and talks
to an AI chatbot. The chatbot is an orchestrator that routes each question to
one of three specialized agents:

  manuals      RAG over the PDF manual of that specific machine
  diagnostics  telemetry, alarms, maintenance tickets, troubleshooting
  commercial   quotations, revisions and orders

All data comes from the dataset in Project-Q2-DataBase/. Every answer is
produced from the data through tools: the agents never answer from memory.
Access is restricted by company (tenant) and by user visibility level.

Design choices are explained in DOCUMENTATION.md.


2. REQUIREMENTS
---------------

  Python 3.11 or newer
  Node.js 18 or newer
  An API key for a language model. The default is Cerebras, whose free tier is
  enough for this project and needs no credit card and no download.


3. INSTALLATION
---------------

3.1 Dataset

    The dataset is not part of this repository: it is given by the course and
    the manuals are AROL teaching copies that must not be redistributed. Put
    the folder in the project root, keeping its name:

        project_q2_s353921_s358966/
            Project-Q2-DataBase/
                AROL_Q2_synthetic_fleet_dataset.xlsx
                manuals/
                    15610_manual_EN.pdf
                    ...

    The two scripts of 3.3 read it from there and write into data/. Nothing in
    the folder is ever modified.


3.2 Language model

    Get a free API key at https://cloud.cerebras.ai, then:

        cp .env.example .env

    and put the key in LLM_API_KEY. Nothing else is needed: the model runs on
    the provider's side. The default model is qwen-3.8-27b. It answers a
    question in about two seconds and is the model we use for the demo.

    Stay on the free tier. Going over its limit returns an error; it is never
    charged.

    Any provider with an OpenAI-compatible API works, because that is the only
    thing the code assumes. Change LLM_MODEL, LLM_BASE_URL and LLM_API_KEY in
    .env to use Groq, OpenRouter or a local Ollama instead; .env.example lists
    the settings for each. The one requirement is TOOL CALLING support: a model
    without it cannot drive the agents. DOCUMENTATION section 9 reports the
    evaluation on the default model, and repeats it on a second provider to
    show that the correctness does not come from one particular model.

3.3 Backend

        python3 -m venv .venv
        source .venv/bin/activate          (Windows: .venv\Scripts\activate)
        pip install -r requirements.txt

    If "python3 --version" is older than 3.11, use the newer interpreter
    explicitly, for example "python3.11 -m venv .venv".

    Build the two data files (needed once, about ten seconds each):

        cd backend
        python load_data.py          Excel workbook  -> data/arol.db
        python build_index.py        manual PDFs     -> data/manual_index.pkl

3.4 Frontend

        cd frontend
        npm install


4. RUNNING
----------

Two terminals:

    1)  cd backend && uvicorn main:app --reload  (backend,  port 8000)
    2)  cd frontend && npm run dev               (frontend, port 5173)

Then open http://localhost:5173 and sign in with the email address of one of
the dataset accounts. The dataset has no credentials, so load_data.py gives
every account the same password, "arol2026" (DEMO_PASSWORD in .env changes it
before the database is built). Suggested accounts:

    elena.fabbri@valgrande.example    (full)        sees everything
    matteo.bonetti@valgrande.example  (technician)  no quotes and orders
    davide.ranieri@valgrande.example  (commercial)  no telemetry, alarms,
                                                    maintenance

A machine page is reached from the fleet list, or directly with the URL
encoded in its QR code:

    http://localhost:5173/machines/15610      (serial number)
    http://localhost:5173/machines/MCH-0001   (machine id)

The QR code of a machine is shown in the "QR code" tab of its page and is
served as a PNG by the backend.


5. EXECUTION PARAMETERS
-----------------------

Copy .env.example to .env to change the defaults:

    LLM_API_KEY     key of the model provider          (no default)
    LLM_MODEL       model name                         (qwen-3.8-27b)
    LLM_BASE_URL    OpenAI-compatible endpoint         (Cerebras)
    LLM_TIMEOUT     seconds to wait for one model call (6)
    DEMO_PASSWORD   password given to every account    (arol2026)
    TODAY           date used as "now" by the agents   (2026-08-05)
    FRONTEND_URL    base URL encoded in the QR codes   (http://localhost:5173)

LLM_TIMEOUT is six seconds because a request on a free tier sometimes stalls,
and retrying is faster than waiting. A slow local model needs a larger value.
DEMO_PASSWORD is read by load_data.py, so change it before building the
database.

TODAY exists because the dataset is a snapshot: telemetry and alarms stop on
2026-08-04, so the README of the dataset asks to treat 2026-08-05 as today.


6. DATASET FORMATS
------------------

Input, unchanged, in Project-Q2-DataBase/:

    AROL_Q2_synthetic_fleet_dataset.xlsx
        One sheet per entity: Companies, Users, MachineModels, Machines,
        Quotes, QuoteRevisions, QuoteLines, Orders, OrderLines,
        TelemetrySnapshots, Alarms, MaintenanceTickets. The first row of each
        sheet holds the column names.

    manuals/<serialNumber>_manual_EN.pdf
        One use-and-maintenance manual per machine. The serial number is the
        join key with the Machines sheet.

Generated, in data/ (both are rebuilt by re-running the two scripts):

    arol.db             SQLite database, one table per sheet, plus the tables
                        Sessions and Messages used for the chat history and
                        Credentials, one hashed password per account.
    manual_index.pkl    TF-IDF index of the manuals: one entry per PDF page
                        with its serial number, page number and text.

Those two files are not in this archive because the two scripts rebuild them
in about ten seconds. The measurement results written next to them are in the
archive, because they are the raw numbers behind DOCUMENTATION section 9:

    data/retrieval_comparison.json   TF-IDF vs embeddings on the manuals:
                                     per question and the summary table
    data/public_benchmark.json       the same two retrievers on SciFact (BEIR)
    evaluation/results_cerebras.json the 14-question run and the routing
                                     repetitions


7. HTTP API
-----------

    POST /api/login                        {"email": "...", "password": "..."}
                                           -> session token
    GET  /api/me                           logged-in user
    GET  /api/machines                     fleet of the user's company
    GET  /api/machines/{ref}               one machine (id or serial number)
    GET  /api/machines/{ref}/manual        manual PDF
    GET  /api/machines/{ref}/qr            QR code of the machine, PNG
    POST /api/chat                         {"message": "...", "machine": "..."}
    GET  /api/chat/history?machine=...     last turns of this session about one
                                           machine, so a reload does not lose them

Every call except /api/login needs the session token, sent as
"Authorization: Bearer <token>". The manual and the QR code accept it as a
query parameter (?token=...) because they are loaded by the browser itself.


8. PROJECT LAYOUT
-----------------

    backend/
        config.py          paths and settings
        load_data.py       Excel workbook  -> SQLite
        build_index.py     manual PDFs     -> TF-IDF index
        db.py              SQLite helpers
        access.py          access model (company + visibility)
        tools.py           the twelve tools the agents can call
        agents.py          the three agents and their tool schemas
        orchestrator.py    routing, access check, tool-calling loop, memory
        llm.py             wrapper around the language model API
        main.py            FastAPI application
    frontend/src/
        main.jsx           routes
        api.js             fetch helper
        Login.jsx          email and password sign-in
        Fleet.jsx          machines of the company
        Machine.jsx        machine page: assistant, manual, QR code
        Chat.jsx           chat panel
        index.css          mobile-first styling
    evaluation/
        functional_checks.py      59 checks of the API, the tools and the
                                  access model; no model call
        retrieval_comparison.py   TF-IDF vs an embedding retriever, twelve
                                  manual questions with page-level ground truth
        public_benchmark.py       the same two retrievers on SciFact (BEIR),
                                  a public benchmark: 5183 documents, 300
                                  queries with public relevance judgements
        make_plots.py             the figures used in DOCUMENTATION.md
    docs/
        figures/           generated PNGs used by DOCUMENTATION.md

    The scripts under evaluation/ are not part of the platform. The functional
    checks need nothing beyond the platform itself, with the backend running:

        cd evaluation
        ../.venv/bin/python functional_checks.py

    The other three need dependencies that are not in requirements.txt. To
    reproduce the retrieval measurements and the figures:

        cd evaluation
        ../.venv/bin/pip install sentence-transformers matplotlib
        ../.venv/bin/python retrieval_comparison.py
        ../.venv/bin/python public_benchmark.py
        ../.venv/bin/python make_plots.py

    public_benchmark.py downloads the dataset (about 3 MB) into data/beir/ on
    its first run.


9. TROUBLESHOOTING
------------------

"The language model is not reachable"
    LLM_API_KEY is missing or wrong in .env, there is no internet connection,
    or the free quota of the day is over. The message returned by the provider
    is shown in the chat.

An answer takes much longer than usual
    On a hosted free tier a request sometimes stalls on the provider's side for
    half a minute or more, at random. backend/llm.py therefore uses a 6 second
    timeout and retries: a stalled request is abandoned and the retry normally
    answers in under a second. A question costs 2 to 4 requests (routing plus
    the agent and its tool rounds), so a turn usually takes 1 to 6 seconds. If
    answers stop completely, the free quota of the day is over.

    After changing llm.py or .env, restart the backend, or start it with
    "uvicorn main:app --reload" so it restarts by itself.

The assistant says it cannot find the machine
    The machine belongs to another company. A user only ever reaches the
    machines of their own company; this is intentional.

The assistant ignores the tools or invents data
    The model configured in LLM_MODEL has no tool-calling support. Check the
    provider's documentation and use a model that supports it.
