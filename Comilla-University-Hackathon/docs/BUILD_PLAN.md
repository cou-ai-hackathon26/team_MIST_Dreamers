# Ek Call: 2-Day Build Plan (Clean Architecture, team of 3)

Team **MIST_Dreamers**. Read together with `SRS.md` (the SRS defines *what*, this file defines *how, who and when*). If the two disagree, the SRS wins. First time on a laptop: `docs/SETUP.md`.

| Member | Name in this plan | Owns (features end to end, see Section 0.2) |
|---|---|---|
| Md. Tamim Hossain | **Tamim** | AI/ML and the backend around it: documents and questions, router (TF-IDF, BanglaBERT, LLM), retrieval, LLM adapters, agent graph, verifier, answer cache, clustering, evaluation. No frontend. Team lead: moves the work to the team repository (D0-1) and keeps `docs/SRS.md` and this plan up to date. |
| Md. Ragib Hossain Rifat | **Ragib** | Voice, on the phone and in the app: Twilio calls, call-back, missed call, signature check, async voice answer (backend); mic input, answer audio, "Call me" button (frontend). |
| Md. Ariful Islam | **Ariful** | Web app, SMS and admin: SMS adapters, background runner, full AskQuestion, admin APIs, demo data (backend); app pages, checklist card, sources, history, admin dashboard with the cluster view (frontend). |

Step IDs (D1-T4, D2-A1, ...) are fixed names from the first version of this plan (A = backend/voice, T = AI/ML, R = data/web). They no longer say who owns a step: the **Owner** column in Section 0.1 does.

---

## 0. How to work with this plan

1. `docs/SRS.md`, `docs/BUILD_PLAN.md` (this file) and `docs/SETUP.md` are committed. Secrets live only in `backend/.env` (git-ignored); keys are shared privately, never committed.
2. Take **one step at a time** from your rows in Section 0.1, in order. Read its section (Section 5 or 6) and the SRS requirements it lists before writing code.
3. **Working loop for every step:** build one small part, make sure you can explain what it does and why in simple words, test that part, then the next small part. One plan step usually has several small parts.
4. A step is finished when its **Done-check** passes and the checks are green: `ruff check .` and `pytest -q` in `backend/`, `npm run build` in `frontend/` for frontend work. Name the step in the pull request title; Tamim updates the Status column in Section 0.1 at the next sync point.
5. Change only files you own (Section 0.4). That is what keeps pull requests free of git conflicts.
6. Git: Section 0.3. Commit messages and pull request titles name the step and the requirement IDs, for example `D1-A3: Twilio voice echo (FR-CALL-01, 03, 04)`.
7. Before Day 1, read the hackathon rulebook part about the pre-build period (for example whether starter code is allowed and whether commit history is checked).

### 0.1 Team build order and progress
Each person follows their own rows top to bottom. A step only needs the steps above it that it names in its section; most rows of different people can run at the same time.

`Weight` = share of the whole project (sums to 100). **Team progress % = sum of the weights of `done` steps** (plus the finished fraction of steps in progress). Steps 1 to 9 (32%) were built before the team split.

| # | Step | What you get | Owner | Weight | Status |
|---|---|---|---|---|---|
| 1 | P1 to P9 | Accounts, keys, models downloaded | Tamim | 3 | done |
| 2 | D1-ALL-1 | Repo skeleton | Tamim | 3 | done |
| 3 | D1-T1 | Domain, ports, fakes, architecture test | Tamim | 4 | done |
| 4 | D1-A1 | Config, DB, container, `/health` | Tamim | 4 | done |
| 5 | D1-A2 | Chat API with a stub engine | Tamim | 3 | done |
| 6 | D1-R1 | Official documents for all 8 services | Tamim | 5 | done (all 5 birth registration documents have real links) |
| 7 | D1-T2 | Embedder, Chroma, ingest | Tamim | 4 | done |
| 8 | D1-R2 | Seed, test and out-of-scope questions | Tamim | 3 | done |
| 9 | D1-T3 | Gemini, Ollama and hybrid LLM adapters | Tamim | 3 | done (live Gemini check passed 21 Nov) |
| 10 | D0-1 | Move the work to the new team repository | Tamim | 0 | done |
| 11 | D1-R4 | Augmented questions + TF-IDF baseline | Tamim | 4 | done (test 89.8%, val 78.8%) |
| 12 | D1-T4 | Agent v1 replaces the stub: Checkpoint 1 in Swagger | Tamim | 7 | done |
| 13 | D1-R3 | App pages + chat page: Checkpoint 1 in the app | Ariful | 4 | done |
| 14 | D1-A3 | Twilio voice, echo mode | Ragib | 4 | done |
| 15 | D1-A4 | SMS adapters, background runner, full AskQuestion | Ariful | 4 | done |
| 16 | D1-T6 | BanglaBERT training on your PC or Colab (runs while you continue) | Tamim | 3 | done (test 93.5%, CPU 13 min) |
| 17 | D1-T5 | Grading, rewrite, verifier, follow-up, fallback | Tamim | 6 | done |
| 18 | D1-A5 | Voice wired to AskQuestion + SMS: Checkpoint 2 | Ragib | 4 | done |
| 19 | D1-R5 | Checklist card, sources, history page | Ariful | 3 | done |
| 20 | D1-R7 | Mic input in the app | Ragib | 1 | done |
| 21 | D1-R6 | App flow tests + demo phrases | Ragib | 1 | done |
| 22 | D2-A1 | Call-back API, missed call, signature check | Ragib | 4 | done |
| 23 | D2-T1 | BanglaBERT adapter + router evaluation | Tamim | 3 | done (93.5%, 95.4% after LLM, 34 ms) |
| 24 | D2-R1 | Admin APIs + dashboard | Ariful | 4 | done |
| 25 | D2-R2 | "Call me" button + answer audio (TTS) | Ragib | 2 | done |
| 26 | D2-A2 | Async voice answer + voice error paths | Ragib | 2 | done |
| 27 | D2-T4 | Answer cache in the agent + pre-warm | Tamim | 1 | done |
| 28 | D2-T2 | K-Means clusters + cluster APIs | Tamim | 2 | done |
| 29 | D2-R5 | Cluster view in the dashboard | Ariful | 1 | done |
| 30 | D2-R4 | App polish, 360 px check, PWA | Ariful | 1 | done |
| 31 | D2-T3 | RAG evaluation + answer check | Tamim | 2 | done (Recall@5 96.9%, refusal 100%, answer check 100% correct, 32 of 32) |
| 32 | D2-R3 | Demo data + scenario checks | Ariful | 1 | |
| 33 | D2-A3 | Voice and API tests + hardening | Ragib | 1 | done |
| 34 | D2-ALL-1 | Full demo rehearsal + fixes | All | 1 | |
| 35 | D2-ALL-2 | README, architecture doc, results, backup video | All | 2 | |

Remaining after the split: Tamim 28, Ragib 19, Ariful 18, all together 3 (Tamim's share is larger because steps 1 to 9 are his groundwork and the agent is the core).

### 0.2 Who owns what

| | Tamim | Ragib | Ariful |
|---|---|---|---|
| **Feature** | The AI agent and its data | Voice: phone and app | Web app, SMS, admin |
| **Backend** | `application/agent/*`, `infrastructure/ml/*`, `llm/*`, `retrieval/*`, `agent/langgraph_engine.py`, cache lookup step, `use_cases/clusters.py` + cluster routes, `data/raw_docs`, `data/questions`, scripts: ingest, ask, augment, train, eval | `interfaces/voice/*` (router, TwiML, signature check), `telephony/twilio_call_placer.py`, `use_cases/start_callback.py`, `handle_call_end.py`, `speech.py`, `tts/gtts_tts.py`, routes `/api/v1/callback` and `/api/v1/tts` | `sms/*`, `background/thread_runner.py`, SMS part of `use_cases/ask_question.py`, `use_cases/admin.py` + admin routes, `scripts/seed_demo_data.py` |
| **Frontend** | none | `useVoiceInput` + `webSpeech.ts` + `MicButton`, `audioPlayer.ts` + play button, `CallMeButton` | app layers, `StartPage`, `ChatPage`, `ExampleChips`, `ChecklistCard`, `SourceList`, `HistoryPage`, `AdminPage`, `ClusterList`, polish, PWA |
| **SRS** | FR-AGT-*, FR-DATA-*, FR-ADM-03, 04 (APIs) | FR-CALL-*, FR-APP-03, 04, 06 | FR-SMS-*, FR-APP-01, 02, 05, 07 to 10, FR-ADM-01, 02, 04 (view), 05, 06 |

**Hand-offs (nobody waits for anybody):**
- The API contract is SRS Section 8. The chat API already runs with `StubAnswerEngine`, so the app, voice and SMS work start now. At Checkpoint 1, Tamim switches `answer_engine` in `container.py` to the real agent; nothing else changes.
- Ragib's voice routes call `container.ask_question` (AskQuestion v1 is already in the repo; Ariful's D1-A4 adds the SMS part without changing how it is called).
- Ragib's mic, answer audio and "Call me" pieces go on Ariful's `ChatPage` without either of them editing the other's files: Ariful creates placeholder components with fixed props in D1-R3 and places them; Ragib then fills those files in (Section 0.4).
- Tamim builds the cluster APIs (D2-T2); Ariful shows them (D2-R5). Ariful builds the admin stats and questions APIs and the admin token check (D2-R1); Tamim's cluster routes reuse that check.

**Files and git conflicts:** see Section 0.4 (who owns which file, and how the few shared files are split).

### 0.3 Git workflow
1. The team repository is the new one from D0-1. Nobody pushes to the old repository any more.
2. `main` always works: `ruff check .`, `pytest -q` and `npm run build` pass on it.
3. One branch per step: `<name>/<step>-<short-name>`, for example `ragib/d1-a3-voice-echo`, `ariful/d1-r3-chat-page`, `tamim/d1-t4-agent`.
4. Before starting a step and again before opening a pull request: `git pull origin main` into your branch, then run the checks.
5. Open a pull request into `main`; another member looks at it (two minutes is enough), then merge when the checks are green. Small pull requests merged often beat one big merge at night.
6. At every sync point and checkpoint (Section 4) everyone merges what works, pulls `main`, restarts the API and the app, and runs the checkpoint test together.
7. Never commit `backend/.env`, keys, `backend/data/models/*`, `backend/data/chroma/`, `*.db` or `node_modules`.
8. A pull request that changes a file owned by someone else (Section 0.4) needs that person's OK in the review.

### 0.4 File ownership (so pull requests do not conflict)
Git only reports a conflict when two branches change the same lines of the same file. So every file has **one owner**, and the few files everyone needs are already split into areas or frozen.

| Owner | Backend (`backend/`) | Frontend (`frontend/src/`) | Other files |
|---|---|---|---|
| Tamim | `app/application/agent/`, `app/infrastructure/` folders `ml/`, `llm/`, `retrieval/`, `agent/`, `cache/`; `use_cases/clusters.py`; `routers/clusters.py`; `scripts/` (except `seed_demo_data.py`); `data/raw_docs/`, `data/questions/`; `app/domain/`; `app/application/ports/` (except `repositories.py`); `requirements.txt` | none | `docs/SRS.md`, `docs/BUILD_PLAN.md`, `docs/SETUP.md`, `docs/architecture.md`, `docs/results/router_eval.md`, `rag_eval.md`, `answer_check.csv`, `ml/` |
| Ragib | `app/interfaces/voice/`; `app/infrastructure/telephony/`, `tts/`; use cases `start_callback.py`, `handle_call_end.py`, `speech.py`; `routers/callback.py`, `routers/tts.py` | every `voice/` folder: `application/voice/`, `infrastructure/voice/`, `presentation/components/voice/` | `docs/results/issues.md` |
| Ariful | `app/infrastructure/sms/`, `background/`, `db/`; `app/application/ports/repositories.py`; use cases `ask_question.py`, `admin.py`; `routers/admin.py`; `scripts/seed_demo_data.py` | everything else: `App.tsx`, `main.tsx`, `config.ts`, `domain/`, `application/` (hooks, `ports.ts`), `infrastructure/apiClient.ts`, `presentation/pages/`, other components; `frontend/package.json`, `index.html`, `public/` | `README.md`, `docs/results/scenario_check.md` |

Tests: put your tests in new files of your own (`tests/unit/test_<thing>.py`, `tests/integration/test_<thing>.py`); do not add to someone else's test file.

**Shared files and how they are split:**

| File | Rule |
|---|---|
| `backend/app/main.py` | Frozen. Every router file already exists and is registered (`voice/router.py`, `callback.py`, `tts.py`, `admin.py`, `clusters.py`). Add routes inside your own router file. |
| `backend/app/container.py` | Three marked areas at the bottom: voice (Ragib), SMS + background + admin (Ariful), AI (Tamim). Add properties only inside your area. Above them, `ask_question` wiring is Ariful's (D1-A4); `answer_engine`, `llm`, `retriever` and `health()` are Tamim's. |
| `backend/app/interfaces/api/schemas.py`, `deps.py` | Frozen (chat, history, services). Put new request/response models and use-case getters in your own router module (or your own `schemas_voice.py` / `schemas_admin.py`), using `get_container` from `deps.py`. |
| `backend/tests/fakes.py` | Every port already has a fake. A new fake goes in your own test file. Changing an existing fake is done by the owner of its port (repositories: Ariful; LLM, retriever, classifier: Tamim; call placer, TTS: Ragib). |
| `backend/app/config.py`, `backend/.env.example` | Every SRS variable already exists. If one must be added, add it at the end of your area's block (`# --- Twilio`: Ragib; `# --- SMS`, `# --- security + privacy`: Ariful; `# --- LLM`, `# --- router + retrieval`: Tamim). |
| `backend/requirements.txt`, `frontend/package.json` | All needed packages are already installed. A new Python package: ask Tamim; a new npm package: ask Ariful. The Web Speech API and audio playback need none. |
| `frontend/src/presentation/pages/ChatPage.tsx` | Ariful's. In D1-R3 he creates three placeholder components in `presentation/components/voice/` that return `null`, with these props, and places them on the page: `MicButton({ onText, disabled }: { onText: (text: string) => void; disabled?: boolean })`, `PlayAnswerButton({ text }: { text: string })` (the answer's `speech_text`), `CallMeButton({ phone }: { phone: string })` (the E.164 number from the session). From then on these three files are Ragib's; nobody needs to touch `ChatPage` for them again. |
| API calls from the app | `ports.ts` and `apiClient.ts` are Ariful's. Ragib's calls (`/api/v1/tts`, `/api/v1/callback`) live in `infrastructure/voice/voiceApi.ts`, reading the base URL from `config.ts`. |
| `docs/BUILD_PLAN.md` Status column, `docs/SRS.md` | Only Tamim edits them (Status at each sync point; the SRS after the team agrees). |

---

## 1. Accounts and keys (before Day 1)

Account sign-ups and verifications are slow, so finish them first.

| # | Task | Owner | Status / done when |
|---|---|---|---|
| P1 | New team GitHub repository (private), add all 3 members, move the work into it (D0-1) | Tamim | Everyone can clone and push |
| P2 | Twilio trial account, voice number, Bangladesh enabled in Geo permissions | Tamim | Done (test call worked). Still to do: verify Ragib's and Ariful's BD numbers (Verified Caller IDs, Tamim gets the code by call); share `TWILIO_*` values with Ragib privately |
| P3 | Google AI Studio: each member creates one Gemini API key and sends it to Tamim privately (3 keys for rotation); note the free Flash and Flash-Lite model names | All | 3 keys in everyone's `.env` |
| P4 | textbee: account, Android app on a phone with a BD SIM and SMS balance, device registered, API key and device ID | Ariful | Test SMS from the textbee dashboard arrives |
| P5 | ngrok: account, install, authtoken; claim the free static domain if offered (the URL then never changes) | Ragib | `ngrok http 8000` gives a public URL |
| P6 | Install Python 3.11, Node 20 LTS, Git, VS Code, Chrome (`docs/SETUP.md`) | All | `python --version`, `node --version` |
| P7 | Hugging Face models: `intfloat/multilingual-e5-small` (every laptop, downloaded by the first ingest), `csebuetnlp/banglabert` (Tamim) | All / Tamim | e5 cached in `backend/data/models/e5` |
| P8 | Official source pages for the 8 services | Tamim | Done (documents collected) |
| P9 | Ollama (optional local LLM): installed, `qwen2.5:7b` pulled | Tamim (others optional) | Done on Tamim's laptop (about 52 tokens/s) |

---

## 2. Engineering rules (everyone)

```markdown
# Ek Call engineering rules

## Architecture (Clean Architecture, strictly)
- backend/app/domain: entities, value objects, enums, policies, Bangla message constants. Standard library only.
- backend/app/application: ports (typing.Protocol), use cases, DTOs, framework-free agent step functions, prompt templates. Imports only app.domain + stdlib.
- backend/app/infrastructure: adapters that implement ports (Gemini, Ollama, Chroma, e5, BanglaBERT, TF-IDF, Twilio, textbee, SQLAlchemy, gTTS, K-Means) and the LangGraph wiring. May import anything.
- backend/app/interfaces: FastAPI routers, request/response schemas, TwiML building. Calls use cases only. No business logic.
- backend/app/container.py is the ONLY place that constructs adapters (composition root). Choose adapters from config (ROUTER_BACKEND, SMS_BACKEND...).
- Never import infrastructure from application or domain. tests/test_architecture.py enforces this; keep it green.
- Tunable values (thresholds, retries, TTLs) come from config.py and are passed in by the container; domain/policies.py holds only the defaults.
- Background or delayed work (SMS, call-back, async voice answer) goes through the BackgroundRunner port, never FastAPI BackgroundTasks or asyncio tasks inside application code.

## Code style
- Python 3.11, type hints everywhere, dataclasses (frozen where possible) in domain.
- pydantic only in interfaces (HTTP schemas) and config.py.
- Small functions, clear names, English code/comments/logs; ALL user-facing text in Bangla from app/domain/messages_bn.py.
- No secrets in code. Read everything from config.py (pydantic-settings, .env).
- Every adapter must fail gracefully: raise a domain error (app/domain/errors.py); interfaces map it to a Bangla message.
- Log with the standard logging module; log timings and llm_calls per question.

## Tests
- pytest; unit tests use fakes from tests/fakes.py (FakeLLM, FakeRetriever, FakeSms, FakeClassifier, FakeRunner, in-memory repos). No network in unit tests.
- Run `ruff check .` and `pytest -q` before every commit; `npm run build` for frontend changes.

## Frontend
- React + Vite + TypeScript + Tailwind. Layers: src/domain (types), src/application (hooks = use cases, ports.ts), src/infrastructure (api client, speech, audio), src/presentation (pages, components).
- Components never call fetch directly; they use hooks, hooks use the ApiPort.
- Theme: Bangladesh flag colours. Use the Tailwind tokens bg-bd-green / bg-bd-red etc. defined in src/index.css, never raw hex in components. Flag red on white only for large text, icons and buttons; use bd-red-dark for small red text.

## Team workflow
- docs/SRS.md defines what to build; docs/BUILD_PLAN.md defines the steps, owners and progress (Section 0.1). If they disagree, the SRS wins.
- Work only on your own steps (Owner column) and change only files you own (Section 0.4). Need a change in someone else's file? Ask them first.
- One plan step at a time, in small parts: build, explain, test, next part.
- Run the step's Done-check before calling a step done; name the step in the pull request title. Tamim updates the Status column at sync points.
- Reference requirement IDs (FR-..., NFR-...) from docs/SRS.md in commits and pull requests.
- One branch per step, pull requests into main (Section 0.3). main must always pass the checks.
```

---

## 3. Folder structure (create in Step D1-ALL-1)

```
ek-call/
├── README.md
├── .gitignore
├── docs/
│   ├── SRS.md
│   ├── BUILD_PLAN.md              # steps, owners, progress
│   ├── SETUP.md                   # first-time setup on a laptop
│   ├── architecture.md            # diagrams for judges (Day 2)
│   └── results/                   # router_eval.md, rag_eval.md (generated)
├── backend/
│   ├── pyproject.toml             # ruff + pytest config
│   ├── requirements.txt
│   ├── .env.example
│   ├── app/
│   │   ├── main.py                # FastAPI app factory, startup (load models once)
│   │   ├── config.py              # pydantic-settings Settings
│   │   ├── container.py           # composition root (builds adapters + use cases)
│   │   ├── domain/
│   │   │   ├── entities.py        # Service, Citation, Checklist, Answer, Message, QuestionLog
│   │   │   ├── value_objects.py   # PhoneNumber, Channel, AnswerStatus, RouterSource
│   │   │   ├── policies.py        # thresholds, max retries, max speech words, sms length
│   │   │   ├── messages_bn.py     # SRS Appendix A strings
│   │   │   └── errors.py          # DomainError, LLMUnavailable, NotFound, InvalidPhone
│   │   ├── application/
│   │   │   ├── ports/
│   │   │   │   ├── classifier.py  # ServiceClassifier
│   │   │   │   ├── retrieval.py   # Embedder, Retriever, Passage
│   │   │   │   ├── llm.py         # LLM
│   │   │   │   ├── engine.py      # AnswerEngine
│   │   │   │   ├── messaging.py   # SmsSender, CallPlacer, TextToSpeech
│   │   │   │   ├── repositories.py# ConversationRepo, ChecklistRepo, QuestionLogRepo, CallRepo, ClusterRepo, AnswerCache
│   │   │   │   ├── clustering.py  # Clusterer
│   │   │   │   └── background.py  # BackgroundRunner
│   │   │   ├── agent/
│   │   │   │   ├── state.py       # AgentState TypedDict
│   │   │   │   ├── steps.py       # classify, llm_classify, cache_lookup, retrieve, grade, rewrite_query, generate, verify, finalize, finalize_follow_up, fallback
│   │   │   │   ├── routing.py     # pure functions that decide the next step
│   │   │   │   └── prompts.py     # prompt templates + JSON schemas (SRS Appendix B)
│   │   │   ├── use_cases/
│   │   │   │   ├── ask_question.py
│   │   │   │   ├── start_callback.py
│   │   │   │   ├── handle_call_end.py
│   │   │   │   ├── history.py     # GetHistory, DeleteHistory
│   │   │   │   ├── admin.py       # GetAdminStats, ListQuestions
│   │   │   │   ├── clusters.py    # RebuildClusters, GetClusters
│   │   │   │   └── speech.py      # SynthesizeSpeech
│   │   │   ├── dto.py
│   │   │   └── formatting.py      # format_sms(checklist) etc. (pure)
│   │   ├── infrastructure/
│   │   │   ├── llm/gemini_llm.py          # key rotation, JSON mode, retries
│   │   │   ├── llm/ollama_llm.py          # local model through Ollama (optional)
│   │   │   ├── llm/routed_llm.py          # LLM_BACKEND=hybrid: FAST -> Ollama, MAIN -> Gemini (+ fallback)
│   │   │   ├── ml/
│   │   │   │   ├── tfidf_classifier.py
│   │   │   │   ├── banglabert_classifier.py
│   │   │   │   ├── llm_classifier.py
│   │   │   │   └── kmeans_clusterer.py
│   │   │   ├── retrieval/
│   │   │   │   ├── e5_embedder.py
│   │   │   │   ├── chroma_retriever.py
│   │   │   │   └── chunker.py
│   │   │   ├── agent/langgraph_engine.py   # wires application/agent/steps into a StateGraph
│   │   │   ├── agent/stub_engine.py        # fixed answer until the real engine exists (D1-A2)
│   │   │   ├── background/thread_runner.py # ThreadPoolRunner (BackgroundRunner port)
│   │   │   ├── telephony/twilio_call_placer.py
│   │   │   ├── sms/textbee_sms.py
│   │   │   ├── sms/console_sms.py
│   │   │   ├── tts/gtts_tts.py
│   │   │   ├── cache/answer_cache.py
│   │   │   └── db/
│   │   │       ├── session.py
│   │   │       ├── models.py               # SQLAlchemy tables (SRS 6.2)
│   │   │       └── repositories.py
│   │   └── interfaces/
│   │       ├── api/
│   │       │   ├── deps.py                 # get use cases from container, admin token check
│   │       │   ├── errors.py               # domain error -> JSON error format
│   │       │   ├── schemas.py              # pydantic request/response models
│   │       │   └── routers/ (health.py, chat.py, history.py, services.py, callback.py, tts.py, admin.py, clusters.py)
│   │       └── voice/
│   │           ├── router.py               # /voice/incoming, /start, /respond, /result, /status
│   │           ├── twiml.py                # pure TwiML builders (greet, answer, reprompt, goodbye)
│   │           └── security.py             # Twilio signature validation
│   ├── scripts/
│   │   ├── check_docs.py                   # checks raw_docs before ingest (D1-R1)
│   │   ├── ingest.py
│   │   ├── search.py                       # try the search by hand (D1-T2)
│   │   ├── tune_retrieval.py               # Recall@5 + score check (Sync 1)
│   │   ├── ask.py                          # ask the agent from the terminal (D1-T4)
│   │   ├── llm_smoke.py                    # Gemini JSON smoke test (D1-T3)
│   │   ├── augment_questions.py
│   │   ├── train_baseline.py
│   │   ├── eval_router.py
│   │   ├── eval_rag.py
│   │   └── seed_demo_data.py               # fills logs so the dashboard is not empty
│   ├── data/
│   │   ├── services.yaml
│   │   ├── raw_docs/<service_id>/*.md
│   │   ├── questions/ (seed.csv, train.csv, val.csv, test.csv, out_of_scope.csv)
│   │   ├── models/ (tfidf_router.joblib, router/)  # git-ignored except .gitkeep
│   │   └── chroma/                                  # git-ignored
│   └── tests/
│       ├── fakes.py
│       ├── test_architecture.py
│       ├── unit/ (test_phone.py, test_policies.py, test_formatting.py, test_agent_routing.py, test_agent_steps.py, test_ask_question.py, test_twiml.py)
│       └── integration/ (test_chat_api.py, test_voice_api.py)
├── ml/
│   ├── train_router.py              # Colab script: fine-tune BanglaBERT
│   └── README.md                    # how to run on Colab, where to put the output
└── frontend/
    ├── package.json, vite.config.ts, tailwind.config.js, index.html, .env.example
    └── src/
        ├── main.tsx, App.tsx (routes: /, /history, /admin), config.ts
        ├── domain/types.ts
        ├── application/ (ports.ts, useSession.ts, useChat.ts, useVoiceInput.ts, useHistory.ts, useAdmin.ts)
        ├── infrastructure/ (apiClient.ts, webSpeech.ts, audioPlayer.ts, storage.ts)
        └── presentation/
            ├── pages/ (StartPage.tsx, ChatPage.tsx, HistoryPage.tsx, AdminPage.tsx)
            └── components/ (MessageBubble, ChecklistCard, SourceList, MicButton, ExampleChips, CallMeButton, StatCard, ServiceBarChart, ClusterList, QuestionsTable)
```

### 3.1 Key dependencies
`backend/requirements.txt` (pin versions after the first successful install with `pip freeze`):
```
fastapi
uvicorn[standard]
pydantic-settings
python-multipart
sqlalchemy>=2
pyyaml
httpx
twilio
google-genai
langgraph
chromadb
sentence-transformers
transformers
scikit-learn
joblib
numpy
pandas
gtts
pytest
ruff
```
Plus, separately:
```
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install git+https://github.com/csebuetnlp/normalizer
```
Frontend: `react-router-dom`, `tailwindcss`, `recharts`.

### 3.2 Commands (Windows PowerShell / Linux)
| Task | Windows | Linux / macOS |
|---|---|---|
| Create venv | `py -3.11 -m venv .venv; .venv\Scripts\Activate.ps1` | `python3.11 -m venv .venv && source .venv/bin/activate` |
| Run API | `uvicorn app.main:app --reload --port 8000` (inside `backend/`) | same |
| Tunnel | `ngrok http 8000` (or `ngrok http --url=<static-domain> 8000`) | same |
| Frontend | `npm run dev` (inside `frontend/`) | same |
| Tests | `ruff check . ; pytest -q` | `ruff check . && pytest -q` |

Tip: test Bangla requests in Swagger (`http://localhost:8000/docs`), not with `curl` in PowerShell (encoding problems).

---

## 4. Team timeline (phases and sync points)

Clock times are targets for the two hackathon days. If you are ahead or behind, keep the order and meet at the sync points.

| When (target) | Tamim (AI/ML + its backend) | Ragib (voice: phone + app) | Ariful (web app, SMS, admin) |
|---|---|---|---|
| **Start** | Commit everything; D0-1 move to the new repo; send keys and private notes | `docs/SETUP.md`; ngrok; Twilio values from Tamim | `docs/SETUP.md`; textbee phone |
| **Sync 0**: everyone has the new repo running, `/health` answers, `pytest -q` green | | | |
| Day 1 morning | D1-T3 live Gemini check; D1-R4 TF-IDF router | D1-A3 voice echo | D1-R3 app pages + chat page (stub engine) |
| Day 1 midday | D1-T4 agent v1, then swap the stub | D1-A5 with the stub engine | D1-A4 SMS, background runner, full AskQuestion |
| **Checkpoint 1** (18:00): a question in the app gives a real RAG answer | | | |
| Day 1 evening | D1-T6 start Colab training; D1-T5 grading, verifier, follow-up | D1-A5 end to end with SMS; D1-R7 mic | D1-R5 checklist card, sources, history |
| Day 1 night | D1-T5 finish; fix answers from the test notes | D1-R6 app flow tests + demo phrases | finish D1-A4 / D1-R5; help testing |
| **Checkpoint 2** (23:00): a phone call answers in Bangla and the SMS arrives; tag `v0.1` | | | |
| Day 2 morning | D2-T1 BanglaBERT adapter + router evaluation | D2-A1 call-back, missed call, signature check | D2-R1 admin APIs + dashboard |
| **Sync 2** (12:00): merge, run S1 to S9 once, list and share out the bugs | | | |
| Day 2 afternoon | D2-T4 cache; D2-T2 clusters + APIs; D2-T3 evaluation | D2-R2 "Call me" + answer audio; D2-A2 async voice | D2-R5 cluster view; D2-R4 polish; D2-R3 demo data |
| 15:30 to 17:00 | D2-T3 answer check (Ragib and Ariful mark answers) | D2-A3 tests + hardening | D2-R3 scenario checks |
| **Checkpoint 3** (17:00): feature freeze, tag `v0.9` | | | |
| 17:00 to 22:00 | D2-ALL-1 rehearsal; D2-ALL-2 architecture doc + results tables | rehearsal; backup video | rehearsal; README |
| **Code freeze** (22:00): tag `v1.0` | | | |

---

## 5. Day 1: step by step

### D0-1: Move the work to the new team repository (Tamim, first; everyone waits for it)
**Why:** from now on the team works in a new repository. Pushing the existing local repository keeps the full history (all step commits), and the private local files (`backend/.env`, downloaded models, `backend/data/chroma/`) stay on the laptop because they were never committed.

1. Commit everything that is ready (`ruff check .` and `pytest -q` green first).
2. On GitHub: create the new **empty** private repository (no README, no .gitignore, no licence) and add Ragib and Ariful as collaborators (Settings > Collaborators).
3. In the existing project folder:
   ```
   git remote rename origin old
   git remote add origin <NEW_REPO_URL>
   git push -u origin main
   git push origin --tags
   ```
4. Check that nothing secret is in the repository: `git ls-files | Select-String "\.env$|\.db$|chroma/|models/"` (PowerShell) or `git ls-files | grep -E "\.env$|\.db$|chroma/|models/"` (Git Bash) must list only `backend/data/models/.gitkeep`.
5. On GitHub: default branch `main`; optionally protect `main` (Settings > Branches: require a pull request before merging).
6. Send the URL to the team. When the new repository is confirmed, remove the old remote: `git remote remove old`.

If the hackathon rules say code written before the event must not carry its history, ask the organisers first; then push a copy with one first commit instead of step 3.

**Done-check:** the new repository shows the full history, `docs/SRS.md`, `docs/BUILD_PLAN.md` and `docs/SETUP.md` are there, and Ragib's and Ariful's fresh clones pass `pytest -q` (Sync 0).

---

### D1-ALL-1: Repository scaffold (Tamim, done)
**Goal:** everyone works on the same skeleton.
1. Create the folder structure from Section 3 with empty `__init__.py` files and `.gitkeep` in data folders.
2. `docs/SRS.md`, `docs/BUILD_PLAN.md` and `.gitignore` (covers `.venv`, `node_modules`, `.env`, `backend/data/chroma`, `backend/data/models/*` except `.gitkeep`, `*.db`, `__pycache__`, `dist`, plus personal local files).
3. `backend/requirements.txt` and `pyproject.toml` (ruff line length 110, pytest `testpaths = ["tests"]`).
4. `frontend`: `npm create vite@latest frontend -- --template react-ts`, add Tailwind, react-router-dom, recharts.
5. Agree on the API contract: SRS Section 8 is final. Everyone builds against it from the start.
6. Branches: one per step, see Section 0.3.

**Done-check:** `pip install -r requirements.txt` works on all 3 laptops; `npm run dev` shows the Vite page.

---

### D1-A1: Config, database, container, health (Tamim, done)
**Requirements:** NFR-SEC-01, NFR-REL-02, SRS 6.2, SRS 9.
1. `app/config.py`: `Settings(BaseSettings)` with every variable from SRS Section 9, defaults that work offline (`ROUTER_BACKEND=tfidf`, `SMS_BACKEND=console`). Write `.env.example`.
2. `infrastructure/db/session.py` (engine, `SessionLocal`, `init_db()` creates tables) and `models.py` (all tables from SRS 6.2).
3. `application/ports/repositories.py` (Protocols) and `infrastructure/db/repositories.py` (SQLAlchemy implementations).
4. `app/container.py`: a `Container` class with lazily built adapters chosen by settings, and properties for each use case. Built once in `main.py` lifespan and stored on `app.state.container`.
5. `interfaces/api/routers/health.py`: `GET /health` checks DB now; LLM, vector DB and router report `"not_configured"` until those adapters exist.
6. `interfaces/api/errors.py`: exception handlers mapping domain errors to the SRS error JSON with Bangla `message_bn`.
7. CORS from `FRONTEND_ORIGINS`.

**Done-check:** `uvicorn app.main:app --reload` starts; `GET /health` returns `{"status":"ok","db":"ok",...}`; `ekcall.db` has all tables.

### D1-A2: Chat API with a stub engine (Tamim, done)
**Requirements:** FR-APP-02 (API side), SRS 8.
1. `interfaces/api/schemas.py`: `ChatRequest`, `ChatResponse` exactly as SRS 8.
2. `interfaces/api/routers/chat.py`: `POST /api/v1/chat` calls `container.ask_question.execute(...)`.
3. Until Tamim's engine is merged (D1-T4), `container` uses `StubAnswerEngine` (in `infrastructure/agent/stub_engine.py`) that returns a fixed Old Age Allowance answer. This lets Ariful and Ragib build against the API immediately.
4. `routers/history.py` (`GET`/`DELETE /api/v1/conversations/{phone}`), `routers/services.py` (`GET /api/v1/services` from `services.yaml`).
5. Integration test `tests/integration/test_chat_api.py` using `TestClient` and fakes.

**Done-check:** in Swagger, `POST /api/v1/chat` with `{"phone":"01712345678","message":"বয়স্ক ভাতা"}` returns the stub answer; the history endpoint shows the message; tests pass.

---

### D1-T1: Domain, ports, fakes, architecture test (Tamim, done)
**Requirements:** SRS 6.1, 7.1, 7.2, AR-01 to AR-06.
1. `domain/value_objects.py`: `PhoneNumber` (normalise `01XXXXXXXXX` / `8801...` / `+8801...` to E.164, validate `^\+8801[3-9]\d{8}$`), enums `Channel`, `AnswerStatus`, `RouterSource` (`banglabert`, `tfidf`, `llm`, `context`).
2. `domain/entities.py`: frozen dataclasses from SRS 6.1. `domain/policies.py` (defaults only; config overrides the tunable ones): `ROUTER_CONFIDENCE_THRESHOLD=0.7`, `RETRIEVAL_MIN_SCORE=0.80`, `MAX_RETRIEVAL_RETRIES=2`, `TOP_K=5`, `MAX_SPEECH_WORDS=45`, `MAX_SMS_CHARS=300`, `MAX_TURNS_PER_CALL=6`, `VOICE_BUDGET_SECONDS=8`, `CALLBACK_COOLDOWN_SECONDS=60`, `CACHE_TTL_HOURS=24`.
3. `domain/messages_bn.py`: SRS Appendix A. `domain/errors.py`: `DomainError`, `LLMUnavailable`, `NotFound`, `InvalidPhone`, `RateLimited`.
4. All ports in `application/ports/*` as `typing.Protocol` (SRS 7.2), including `BackgroundRunner`. `Passage` dataclass: `chunk_id, service_id, title, source_url, text, score`.
5. `application/formatting.py`: `format_sms(checklist, service) -> str` (cut to 300 chars, keep line order from SRS 3.2) and `trim_speech(text, max_words)`.
6. `tests/fakes.py` (including an inline `FakeRunner`) and `tests/test_architecture.py` (walks `app/` files with `ast`, fails on forbidden imports per AR-01 to AR-04).
7. Unit tests: phone normalisation, `format_sms`, `trim_speech`.

**Done-check:** `pytest -q` green, including the architecture test.

### D1-T2: Embedder, Chroma retriever, ingest (Tamim, done)
**Requirements:** FR-AGT-05, FR-DATA-03.
1. `infrastructure/retrieval/e5_embedder.py`: `sentence-transformers` with `intfloat/multilingual-e5-small`; add `"query: "` prefix for queries and `"passage: "` for passages; normalise embeddings.
2. `infrastructure/retrieval/chunker.py`: parse YAML front matter, split by markdown headings, pack small sections of one document together, cut long sections at about 160 words with 40 overlap (300 words of Bangla is more than e5's 512 tokens); `chunk_id = f"{service_id}-{n:03d}"`.
3. `infrastructure/retrieval/chroma_retriever.py`: `chromadb.PersistentClient(path=CHROMA_DIR)`, collection `ek_call_docs` with cosine space; we pass our own embeddings. `search(query, service_id, k)` uses `where={"service_id": ...}` when given; score = 1 - distance. If fewer than 2 results are above `RETRIEVAL_MIN_SCORE` (from config, start at 0.80), also search without the filter and merge. e5 cosine scores sit close together (often 0.7 to 0.9 even for unrelated text), so tune the threshold on real questions at Sync 1.
4. `scripts/ingest.py`: reads `data/raw_docs/**.md` + `services.yaml`, rebuilds the collection, prints chunks per service.

**Done-check:** `python -m scripts.ingest` prints chunk counts; a small script/test searching "বয়স্ক ভাতার বয়স কত" returns an old-age passage first.

---

### D1-R1: Collect official documents (Tamim, done; 3 birth registration links still to add)
**Requirements:** FR-DATA-01, FR-DATA-02.
1. Write `data/services.yaml` (9 labels from SRS 1.2, with `name_bn`, `name_en`, `office_bn`, `sms_name`).
2. For each of the 8 services, copy the official text (Citizen Charter rows, service pages of the Department of Social Services, birth registration office, Election Commission, Department of Immigration and Passports, land and local government portals) into `data/raw_docs/<service_id>/<slug>.md`:
   ```markdown
   ---
   title: বয়স্ক ভাতা কার্যক্রম: যোগ্যতা ও আবেদন
   source_url: https://...
   office: উপজেলা সমাজসেবা অফিস
   collected_on: 2026-11-21
   ---
   ## যোগ্যতা
   ...
   ## প্রয়োজনীয় কাগজপত্র
   ...
   ## ফি
   ...
   ## কোথায় আবেদন
   ...
   ```
3. Keep official wording; clean menus/ads; use headings: যোগ্যতা, কাগজপত্র, ফি, সময়, কোথায়/কিভাবে আবেদন, সিদ্ধান্ত. 1 to 3 documents per service is enough.
4. Priority order if time is short: old age, widow, birth registration, NID correction, then the rest.

**Done-check:** 8 folders with at least one document each; every file has `source_url`. Push.

### D1-R2: Question seed and test sets (Tamim, done)
**Requirements:** FR-DATA-04.
1. `data/questions/seed.csv`: about 15 questions per label (including `other`), real everyday Bangla, some Banglish, some with spelling mistakes.
2. `data/questions/test.csv`: a **different** set of about 12 per label with different wording and angles from the seed set (no near-copies). Never augment it.
3. `data/questions/out_of_scope.csv`: 25 questions outside the 8 services (land disputes, weather, cricket, medical advice, bank loans) for safe-refusal testing.

**Done-check:** CSVs open in Excel with Bangla shown correctly (UTF-8 with BOM if needed for Excel only; keep UTF-8 in repo).

---

### Sync 1 (done before the split)
- Ingest ran on the real documents: 97 passages. Recall@5 on `test.csv` is 94.8% (`python -m scripts.tune_retrieval`).
- In-scope and off-topic scores overlap (medians 0.867 and 0.836), so `RETRIEVAL_MIN_SCORE` stays 0.80; it only decides when to also search all services. Refusing off-topic questions is the job of the router's `other` label and of grading (D1-T4, D1-T5).
- Every new laptop runs `python -m scripts.ingest` once and puts real keys in its own `.env` (`docs/SETUP.md`).

---

### D1-T3: Gemini + Ollama adapters (Tamim, done; live Gemini check waits for keys)
**Requirements:** FR-AGT-16, FR-AGT-18, C-05, C-06.
1. `infrastructure/llm/gemini_llm.py` implementing `LLM` with the `google-genai` SDK: `generate_json(prompt, schema, model_role)` uses JSON output with a response schema; `model_role` selects `GEMINI_MODEL_MAIN` or `GEMINI_MODEL_FAST`.
2. Key rotation: list from `GEMINI_API_KEYS`; on 429 / quota error switch to next key; one retry with 1 s back-off; then raise `LLMUnavailable`.
3. Count calls (for `llm_calls`) and time them.
4. Low temperature (0.1 to 0.2) for grading, verification, classification.
5. A tiny script `python -m scripts.llm_smoke` asking for a JSON object in Bangla.
6. `check()`: list models with the current key (no generation), result cached for 60 s; `/health` uses it (NFR-REL-02, S9).
7. `infrastructure/llm/ollama_llm.py` implementing `LLM` with `httpx`: `POST {OLLAMA_URL}/api/chat`, `stream=false`, the JSON schema in `format`, `keep_alive` so the model stays loaded (the first call takes about 10 s to load it); connection errors and timeouts raise `LLMUnavailable`; `check()` calls `GET /api/tags` and confirms `OLLAMA_MODEL` is listed.
8. `infrastructure/llm/routed_llm.py` for `LLM_BACKEND=hybrid`: FAST role -> Ollama, MAIN role -> Gemini, and MAIN falls back to Ollama when Gemini raises `LLMUnavailable`. The container picks `GeminiLLM`, `OllamaLLM` or `RoutedLLM` from `LLM_BACKEND`.
9. Prompts must ask for Bangla digits (৬৫, not 65) in `speech_text` (NFR-USE-01): in the first test, `qwen2.5:7b` answered with Latin digits.

**Done-check:** smoke script returns valid JSON; forcing a bad first key still works via rotation; the same smoke script works with `LLM_BACKEND=ollama` and `LLM_BACKEND=hybrid`.

### D1-T4: Agent steps + LangGraph v1 (Tamim)
**Requirements:** FR-AGT-01 to 05, 08, 12, 13, 17; SRS 7.4; SRS Appendix B.
1. `application/agent/state.py`: `AgentState` TypedDict (SRS 7.4).
2. `application/agent/prompts.py`: prompt templates and JSON schemas for `llm_classify`, `grade`, `rewrite`, `generate`, `verify` (rules from SRS Appendix B). Passages are given as `[P1] title: text` so claims can cite `P1`.
3. `application/agent/steps.py`: pure functions `(state, deps) -> partial state`. `deps` is a small dataclass holding ports (classifier, retriever, llm, services). v1 = `classify -> (llm_classify) -> retrieve -> generate -> finalize`, `fallback` for `other` / `no_answer` (the rewrite loop comes in D1-T5). `classify` handles a pending follow-up (FR-AGT-17: if the last assistant message in `history` has status `follow_up`, reuse its `service_id` with `router_source = context`). `llm_classify` gets the router's top 3 and the last 3 turns (FR-AGT-03).
4. `application/agent/routing.py`: pure functions deciding the next node (easy to unit test).
5. `infrastructure/agent/langgraph_engine.py`: builds `StateGraph(AgentState)`, adds nodes as small lambdas calling `steps` with injected deps, adds conditional edges using `routing`, compiles once; `answer()` invokes it and maps the final state to the domain `Answer`.
6. Until BanglaBERT exists, `ROUTER_BACKEND=tfidf` (baseline from D1-R4) or `llm`. Build `infrastructure/ml/llm_classifier.py` here (for `ROUTER_BACKEND=llm`), reusing the `llm_classify` prompt from `prompts.py`.
7. Unit tests with `FakeLLM` for routing decisions and the fallback path.

**Done-check:** a script `python -m scripts.ask "আমার বয়স ৬৭, বয়স্ক ভাতা পাবো?"` prints service, Bangla speech text, checklist, citations.

---

### D1-A3: Twilio voice v1, echo mode (Ragib)
**Requirements:** FR-CALL-01, 03, 04, SRS 3.1.
1. `interfaces/voice/twiml.py`: pure builders using `twilio.twiml.voice_response.VoiceResponse`: `greet()`, `answer_and_listen(text)`, `reprompt()`, `goodbye()`. Every listen uses `Gather(input="speech", language=STT_LANGUAGE, speech_timeout="auto", action="/voice/respond", action_on_empty_result=True)` with `<Say voice=TTS_VOICE language=TTS_LANGUAGE>` **inside** the Gather (barge-in).
2. `interfaces/voice/router.py`: `/voice/incoming` (greet), `/voice/start` (greet, for outbound), `/voice/respond` (echo the `SpeechResult` for now), `/voice/status` (204). Citizen number: `From` for inbound, `To` when `Direction` starts with `outbound`.
3. Silence counter per `CallSid` (in memory dict is fine) for REPROMPT then GOODBYE.
4. Run `ngrok http 8000`, set `PUBLIC_URL`, set the Twilio number's "A call comes in" webhook to `POST {PUBLIC_URL}/voice/incoming`. The number has one webhook, so it reaches one laptop at a time: Ragib's during development, the demo laptop for the demo. Tamim shares the `TWILIO_*` values privately (P2).
5. Unit tests: TwiML snapshots in `test_twiml.py`.

**Done-check:** call the Twilio number from a verified phone; hear the Bangla greeting; speak; hear your own words repeated. If Twilio's debugger shows error 13331 (invalid language), switch `STT_LANGUAGE` to `bn-IN` and retry.

### D1-A4: SMS adapters, background runner, full AskQuestion (Ariful)
**Requirements:** FR-SMS-01 to 05, NFR-PRIV-01.
1. `infrastructure/sms/console_sms.py` (logs the SMS) and `textbee_sms.py`: `POST https://api.textbee.dev/api/v1/gateway/send-sms`, header `x-api-key`, JSON `{"recipients": [phone], "message": text}` (add `deviceId` if your account has several devices), timeout 10 s, returns bool, never raises to the caller.
2. `infrastructure/background/thread_runner.py`: `ThreadPoolRunner` implementing the `BackgroundRunner` port (`submit(fn, *args, delay_s=0)`, a small thread pool, exceptions logged and never raised to the caller); built in `container.py`. Ragib's call-back (D2-A1) and async voice answer (D2-A2) use it too.
3. `application/use_cases/ask_question.py` (AskQuestion v1 already saves messages, logs and checklists; this step adds the SMS part) `AskQuestion.execute(phone, text, channel, call_sid=None) -> AnswerDTO`:
   - normalise phone; load the last 6 messages (with `status` and `service_id`) as history, so the agent can see a pending follow-up (FR-AGT-17);
   - `engine.answer(...)`; measure latency (the answer cache is not checked here: it sits inside the agent after `classify`, see D2-T4);
   - save user + assistant messages, a `QuestionLog` (phone hashed with salt), and the checklist if answered;
   - if `channel == voice` and answered and no SMS yet for `(call_sid, service_id)`: mark `sms_sent`, then submit `sms.send` to the `BackgroundRunner` port (marking first means a slow or failed send can never cause a second SMS; failures are only logged).
4. Unit tests with fakes: SMS sent once per service per call; fallback answers never send SMS; logs contain no raw phone.

**Done-check:** `pytest -q` green; with `SMS_BACKEND=textbee`, a manual test sends a Bangla SMS to a verified phone.

---

### D1-R3: App pages + chat page (Ariful)
**Requirements:** FR-APP-01, 02, 07, 08; SRS 3.3.
1. `src/domain/types.ts` mirroring `ChatResponse`, `Checklist`, `Citation`, `Service`.
2. `src/application/ports.ts` (`ApiPort`), `src/infrastructure/apiClient.ts` (fetch implementation using `VITE_API_URL`).
3. Hooks: `useSession` (phone in localStorage, normalisation), `useChat` (messages, send, loading, error).
4. Pages: `StartPage` (phone input), `ChatPage` (messages, input, example chips). Big fonts, mobile-first, Bangla labels, Bangladesh flag colour theme (tokens in `index.css`).
5. Create the three voice placeholders and put them on `ChatPage` (Section 0.4): `presentation/components/voice/MicButton.tsx`, `PlayAnswerButton.tsx`, `CallMeButton.tsx`, each returning `null` with the agreed props. Ragib fills them in later.
6. Works against the stub engine already in the API, so it does not wait for the agent. Already in the repo: Vite + React + TypeScript, Tailwind v4 with the flag colour tokens in `src/index.css`, react-router-dom and recharts installed, a placeholder `App.tsx`. Add `frontend/.env.example` with `VITE_API_URL=http://localhost:8000`.

**Done-check:** enter a phone number, ask a question, see the stub answer in a bubble.

### D1-R4: Augment questions + TF-IDF baseline (Tamim)
**Requirements:** FR-DATA-05, FR-DATA-06.
1. `scripts/augment_questions.py`: for each seed, ask the LLM (fast model) for 8 variants (casual, misspelt, Banglish, speech-recognition-like errors, short, long); batch 5 seeds per call to save quota; dedupe; write `train.csv` / `val.csv` (90/10 split **by seed**, so variants of one seed stay together). Split the seeds first, then augment each side (FR-DATA-05). Use `GeminiLLM` from D1-T3 for key rotation; if it is not ready, the script may call `google-genai` directly (scripts are outside the architecture layers). To save Gemini quota, `OllamaLLM` can generate the variants instead: read 20 of them first to check the Bangla quality.
2. `scripts/train_baseline.py`: TF-IDF (`analyzer="char_wb"`, `ngram_range=(2,5)`) + `LogisticRegression(max_iter=2000, class_weight="balanced")`; print val accuracy; save `data/models/tfidf_router.joblib` (pipeline + label list).
3. `infrastructure/ml/tfidf_classifier.py` loading the joblib and returning sorted `(label, prob)` pairs.

**Done-check:** baseline val accuracy printed; `ROUTER_BACKEND=tfidf` works in the agent.

---

### Checkpoint 1 (18:00 to 19:00, all)
Merge to `main`. Tamim replaces `StubAnswerEngine` with `LangGraphAnswerEngine` in the container; Ariful checks it in the app.
**Must work:** in the web app, "আমার বয়স ৬৭। বয়স্ক ভাতা পাবো? কী কী লাগবে?" returns a real Bangla answer with a checklist and at least 1 source.
**Cut-line if not working by 19:30:** drop grading for now and run `retrieve -> generate -> finalize` only.

---

### D1-T5: Grading, rewrite, verifier, safe fallback (Tamim)
**Requirements:** FR-AGT-06, 07, 09, 10, 11, 13, 14.
1. Add `grade` (one call for all passages, returns relevant IDs), `rewrite_query` (fast model), retry counter, `verify` (one call: each claim -> supported / unsupported with passage IDs), `finalize` (drop unsupported non-core claims, add `DECISION_NOTE`, trim speech to 45 words, attach citations of used passages only), `finalize_follow_up`.
2. Voice fast mode (`VOICE_FAST_MODE=true` and `channel == voice`): skip `grade`; the generate prompt itself must return `no_answer` if passages are irrelevant, and `no_answer` then follows the same rule as an empty grade (rewrite while retries < 2, else fallback; one shared retries counter). Target: 2 LLM calls per voice question (generate + verify).
3. Include `history` (last 3 turns) in `generate` so follow-up answers work (S2).
4. Record `timings[step]` and `llm_calls`.
5. Unit tests for each routing branch (relevant / rewrite / give up; verified / unsupported retry / fallback).

**Done-check:** S1, S2 (follow-up), S7 (fallback text exactly) work through `scripts.ask`.

### D1-T6: BanglaBERT training on your PC or Colab (Tamim; training runs while you continue)
**Requirements:** FR-DATA-07.
1. `ml/train_router.py`: load `train.csv`, `val.csv`; normalise text with the csebuetnlp `normalize()`; tokenizer + `AutoModelForSequenceClassification.from_pretrained("csebuetnlp/banglabert", num_labels=9)`; a plain PyTorch loop (AdamW, linear warm-up, batch 32, max length 64; no `datasets`/`accelerate` needed), eval each epoch, keep best by macro-F1; report test.csv; save model, tokenizer, `labels.json` into `backend/data/models/router/`. Runs on a normal CPU (about 10 to 20 minutes) and uses a GPU automatically if there is one.
2. `ml/README.md`: how to run it on your PC (recommended) or on Colab, and how to share the model folder through Google Drive (it is not committed).

**Done-check:** the run prints val accuracy and macro-F1 per epoch and the test result; `backend/data/models/router/` holds the model and `labels.json`.

---

### D1-A5: Voice wired to AskQuestion + SMS (Ragib)
Start with the stub engine (it works before Checkpoint 1). The SMS part needs Ariful's D1-A4; until it is merged, `SMS_BACKEND=console` prints the SMS.

**Requirements:** FR-CALL-02, 05, 06, 09, 11; FR-SMS-01, 04.
1. `/voice/respond`: call `AskQuestion` with `channel=voice` and `call_sid`. Speak `answer.speech_text`, add `SMS_SENT` when an SMS was scheduled, then the CONTINUE prompt, all inside the next `<Gather>`.
2. Status `follow_up`: speak the follow-up question and listen.
3. Goodbye words (not while a follow-up question is pending, so "না" counts as an answer) and 6-turn limit; `ERROR` on exceptions (call stays alive).
4. `calls` table rows on start/status callback (configure the status callback URL `POST {PUBLIC_URL}/voice/status` on the number or in `calls.create`).
5. Log voice latency per turn.

**Done-check:** a real call: ask S1, hear a correct short answer, receive the SMS within a minute.

### D1-R5: Checklist card, sources, history (Ariful)
**Requirements:** FR-APP-02, 05; SRS 3.3.
1. `ChecklistCard` (who / papers / fee / where / decision with icons), `SourceList` (title + link), service tag, `follow_up_question` shown as a highlighted question.
2. `HistoryPage` using `GET /api/v1/conversations/{phone}`.

**Done-check:** ask a question, see the answer card with sources; history shows past checklists (including the ones from phone calls).

### D1-R7: Mic input in the app (Ragib)
**Requirements:** FR-APP-03.
1. `infrastructure/voice/webSpeech.ts` + `application/voice/useVoiceInput.ts` (Web Speech API, `lang = "bn-BD"`, interim results shown, auto-send on end). Hide the mic if unsupported (non-Chrome).
2. Fill in `presentation/components/voice/MicButton.tsx`, Ariful's placeholder that is already on `ChatPage` (needs D1-R3 merged). Do not edit `ChatPage`.

**Done-check:** speak a question in Chrome, see the transcript, get the answer card; the mic is hidden in Firefox.

### D1-R6: App flow tests + demo phrases (Ragib)
1. Try S1, S2, S4, S5, S7 in the app; note any wrong answers in `docs/results/issues.md` for Tamim.
2. Prepare a printed list of demo questions (Bangla) for each service.

### Checkpoint 2 (23:00, all)
**Must work:** phone call answers in Bangla using the agent, and the SMS arrives. App works end to end.
Merge, run `pytest -q`, tag `v0.1`, push. Write tomorrow's top 3 risks in `docs/results/issues.md`.

---

## 6. Day 2: step by step

### D2-A1: Call-back, missed call, Twilio security (Ragib)
**Requirements:** FR-CALL-07, 08, 12.
1. `infrastructure/telephony/twilio_call_placer.py`: `client.calls.create(to=phone, from_=TWILIO_NUMBER, url=f"{PUBLIC_URL}/voice/start", status_callback=f"{PUBLIC_URL}/voice/status")`.
2. Use case `StartCallback` + `POST /api/v1/callback` (rate limit: one call per number per 60 s; a repeat returns HTTP 429 with `RATE_LIMITED`).
3. Missed-call mode in `/voice/incoming`: `<Reject/>` then submit `StartCallback` to the `BackgroundRunner` with `delay_s=3`. Test this early: on a trial account the trial notice may play before our TwiML, so the call can be answered (and charged) instead of rejected; if so, demo the call-back with "Call me".
4. `interfaces/voice/security.py`: validate `X-Twilio-Signature` with `RequestValidator(TWILIO_AUTH_TOKEN)` using the full URL Twilio called (`PUBLIC_URL` + path + query string, for example `/voice/result?job=...`) and the form params; 403 on failure when enabled.
5. Note for the demo: trial calls play a Twilio trial message first and may ask the listener to press a key.

**Done-check:** "Call me" from Swagger rings a verified phone and the conversation works; missed-call mode calls back; a forged POST gets 403.

### D2-T1: BanglaBERT adapter + router evaluation (Tamim)
**Requirements:** FR-AGT-02, 03; FR-DATA-08; NFR-PERF-03.
1. `infrastructure/ml/banglabert_classifier.py`: load once from `ROUTER_MODEL_DIR`, apply the same normaliser, softmax, return sorted `(label, prob)`; CPU `torch.inference_mode()`.
2. Switch `.env` to `ROUTER_BACKEND=banglabert`; `/health` shows `router: banglabert`. (`llm_classifier.py` already exists from D1-T4.)
3. `scripts/eval_router.py`: accuracy, macro-F1, per-class F1, confusion matrix for TF-IDF vs BanglaBERT on `test.csv`; also accuracy after the LLM fallback; write `docs/results/router_eval.md` with a table.

**Done-check:** router eval file exists; inference under 200 ms (print timing).

### D2-R1: Admin APIs + dashboard (Ariful)
**Requirements:** FR-ADM-01, 02, 05; SRS 3.4.
1. Backend first: use cases `GetAdminStats` and `ListQuestions` (`use_cases/admin.py`, using `QuestionLogRepo`), routes in the already registered `routers/admin.py`: `GET /api/v1/admin/stats` and `GET /api/v1/admin/questions?status=fallback` (SRS 8); the `X-Admin-Token` check as a FastAPI dependency `require_admin_token` in the same file, used when `ADMIN_TOKEN` is set (Tamim's `clusters.py` imports it); integration tests.
2. `AdminPage`: KPI cards, questions per service bar chart (recharts), voice vs app, recent activity, unanswered table. `X-Admin-Token` from `VITE_ADMIN_TOKEN`.
3. Auto-refresh every 10 s.
4. Write `scripts/seed_demo_data.py` now (D2-R3 item 1): the dashboard and Tamim's clusters (D2-T2) need data.

**Done-check:** after a few questions, the dashboard numbers change; a wrong admin token gets 401.

### Sync 2 (12:00 to 13:00)
Merge everything; full run of S1 to S9 once; list bugs; reassign.

---

### D2-A2: Async voice answer + voice error paths (Ragib)
**Requirements:** FR-CALL-10, NFR-PERF-01, NFR-REL-01.
1. Measure voice latency from logs. **If median > 6 s or any turn > 10 s**, implement the async pattern: `/voice/respond` submits the agent run to the `BackgroundRunner` with a job ID, returns `WAIT_FILLER` + `<Redirect method="POST">/voice/result?job=ID</Redirect>`; `/voice/result` returns the answer if ready, otherwise `<Pause length="2"/>` + redirect again (max 5 times, then ERROR).
2. Check every adapter failure path in a call gives a Bangla message and keeps the call alive (S9).

**Done-check:** S9 passes; with an artificial 10 s delay in the engine, the call still gets its answer.

### D2-T4: Answer cache in the agent + pre-warm (Tamim)
**Requirements:** FR-AGT-15.
1. `infrastructure/cache/answer_cache.py` (SQLite table with 24 h TTL, so pre-warming survives a restart) already exists. Add the `cache_lookup` agent step after `classify` (key = normalised text + service + channel, only when the local router was confident; `finalize` stores only `answered` results).
2. Pre-warm it with the demo questions (cuts latency and quota use during judging). For voice, ask each demo question once in a real call during rehearsal, because Twilio's transcript rarely matches the typed text exactly.

**Done-check:** demo questions answer in under 3 s from the cache.

### D2-T2: K-Means clusters + cluster APIs (Tamim)
**Requirements:** FR-ADM-03, 04.
1. `infrastructure/ml/kmeans_clusterer.py`: scikit-learn `KMeans(n_init=10)`; choose k in 3 to 8 by silhouette score (fixed k=3 when fewer than 30 questions).
2. Use case `RebuildClusters`: embed all logged question texts (`Embedder.embed_query`), cluster, label each cluster with one fast-LLM call ("give a 3 to 5 word Bangla label for these questions") or top TF-IDF terms if the LLM is unavailable; store in `clusters` and set `question_logs.cluster_id`.
3. `POST /admin/clusters/rebuild`, `GET /admin/clusters` in the already registered `routers/clusters.py`, protected by `require_admin_token` from `routers/admin.py` (Ariful, D2-R1).

**Done-check:** after `scripts.seed_demo_data` (Ariful, D2-R1), rebuild returns sensible clusters (for example NID spelling, allowance not received).

### D2-R2: "Call me" button + answer audio (Ragib)
**Requirements:** FR-APP-04, 06; FR-CALL-07.
1. TTS backend: `GttsTts` adapter (`infrastructure/tts/gtts_tts.py`, port `TextToSpeech`), use case `SynthesizeSpeech`, `POST /api/v1/tts` (SRS 8) returning MP3.
2. App: `infrastructure/voice/voiceApi.ts` (calls `/api/v1/tts` and `/api/v1/callback`) and `infrastructure/voice/audioPlayer.ts`; fill in the placeholder `PlayAnswerButton.tsx`; fall back to `speechSynthesis` with a Bengali voice if the endpoint fails.
3. Fill in the placeholder `CallMeButton.tsx`: calls `POST /api/v1/callback` (D2-A1), with the Bangla message for the 429 case. Both buttons are already on `ChatPage`.

**Done-check:** the play button reads an answer aloud; "Call me" rings the verified phone.

### D2-R5: Cluster view in the dashboard (Ariful)
**Requirements:** FR-ADM-04.
1. `ClusterList` (label, size, 3 examples) + a "Rebuild" button calling Tamim's `POST /api/v1/admin/clusters/rebuild` (D2-T2), then `GET /api/v1/admin/clusters`.

**Done-check:** after seeding demo data, Rebuild shows sensible clusters.

### D2-R4: App polish, 360 px check, PWA (Ariful)
**Requirements:** FR-APP-08, 10.
1. Bangla copy, loading animation, error toasts, layout check at 360 px width. PWA manifest + icon (COULD).

### D2-A3: Voice and API tests + hardening (Ragib)
1. Integration tests for `/voice/respond` (fake engine) and `/api/v1/chat`.
2. `VALIDATE_TWILIO_SIGNATURE=true` for the demo; CORS check; `.env.example` complete.
3. Startup check: missing model/collection gives a clear log message, not a crash.

### D2-T3: RAG evaluation + answer check (Tamim)
**Requirements:** FR-DATA-09, SRS 11.
1. `scripts/eval_rag.py`: Recall@5 on `test.csv` (gold = label), safe-refusal rate on `out_of_scope.csv`, average LLM calls and latency; write `docs/results/rag_eval.md`.
2. Answer correctness: run 30 test questions, export answers + passages to `docs/results/answer_check.csv`; Ragib and Ariful mark correct / incorrect (respect the free LLM quota; use the cache).
3. Fix the top prompt issues found.

### D2-R3: Demo data + scenario checks (Ariful)
1. `scripts/seed_demo_data.py` (written early, in D2-R1): insert about 60 realistic question logs over the past week across services and channels (so the dashboard and clusters look alive). Set `is_demo = true` on these rows so they can be filtered or deleted, and say in the demo that the history is sample data.
2. Run S1 to S9 and fill `docs/results/scenario_check.md` (pass / fail + notes).

### Checkpoint 3: feature freeze (17:00)
Only bug fixes after this point. Merge, `pytest -q`, tag `v0.9`.

### D2-ALL-1: Full demo rehearsal + fixes (all, 17:00 to 20:00)
1. Run the demo script (Section 8) three times end to end, with a timer.
2. Fix only demo-breaking bugs. Re-check SMS balance, Twilio credit, Gemini quota.

### D2-ALL-2: Documentation + backup (all, 20:00 to 22:00)
1. Ariful: `README.md`: what it is, architecture picture, setup (Section 3.2), env vars, how to run ingest / train / eval, demo steps.
2. Tamim: `docs/architecture.md`: the layer diagram, agent graph (from SRS 7.4), ports table, why clean architecture (swap Twilio for a BD telecom IVR or Gemini for another LLM by changing one adapter).
3. Tamim: results tables from `docs/results/` (router BanglaBERT vs TF-IDF, Recall@5, refusal rate, latency).
4. Ragib, with everyone: record a 3-minute backup video of S1 (phone + SMS), S4 (app), S6 (dashboard), S7 (fallback) in case the venue network fails.

### Code freeze (22:00)
Tag `v1.0`, push, and copy the repo, `.env`, `data/models/router/` and `data/chroma/` to a USB drive.

---

## 7. Priorities and cut-lines

| Priority | Features |
|---|---|
| **MUST** (protect at all costs) | App chat with RAG answer + checklist + sources; mic input and history in the app; phone call answering in Bangla; "Call me" call-back (FR-CALL-07, FR-APP-06); SMS checklist; safe fallback; verifier; query rewrite + retry (FR-AGT-07); TF-IDF router + LLM classify below the threshold; BanglaBERT trained and evaluated; basic dashboard stats + unanswered list |
| **SHOULD** | Missed-call mode; follow-up question with service carry-over; passage grading; K-Means clusters; async voice answer; cache; Twilio signature check; TTS in app |
| **COULD** | OTP for family history; PWA install; dashboard auto-refresh; "send to my phone" button |

| If at... | ...this is not working | Then |
|---|---|---|
| Checkpoint 1 | Full agent graph | Ship `retrieve -> generate -> finalize` and add grading/verifier in D1-T5 |
| Checkpoint 2 | Twilio calls to BD (trial limits, geo permission) | Keep debugging max 1 h on Day 2 morning; otherwise demo voice through the app mic + TTS and show the Twilio call from a verified number only |
| Checkpoint 2 | textbee SMS | Use `SMS_BACKEND=console` and show the SMS text on the dashboard/app; fix on Day 2 |
| Day 2 12:00 | BanglaBERT model | Keep TF-IDF + LLM router live; show the BanglaBERT training curve and eval table anyway |
| Day 2 15:30 | Clusters | Show per-service counts and the unanswered list only |
| Any time | Gemini quota exhausted | Rotate keys, rely on the pre-warmed cache, reduce eval size; switch to `LLM_BACKEND=hybrid` (or `ollama` as a last resort) |

---

## 8. Demo script (5 to 7 minutes)

1. **Problem (30 s):** Abdul Karim, 67, button phone, no internet (one slide or just say it).
2. **Phone call (2 min):** press "Call me" in the app for a verified phone (or call the number). Ask S1 in Bangla on speaker. Show the SMS arriving on the button phone (or the textbee phone).
3. **Follow-up (30 s):** S2 to show the agent asking about residence.
4. **App (1 min):** open History with the same number (shared memory, UC5); ask S4 by voice; show sources.
5. **Safety (30 s):** S7: the agent refuses and points to 333.
6. **Dashboard (1 min):** stats, clusters, unanswered list.
7. **Under the hood (1 min):** architecture slide, BanglaBERT vs TF-IDF table, verifier, clean architecture (swap adapters by config).

Checklist before going on stage: laptop charged, hotspot on, ngrok URL matches Twilio webhook and `PUBLIC_URL`, `/health` all ok, textbee phone online with balance, Twilio credit left, cache pre-warmed, Ollama running with the model loaded (if `LLM_BACKEND` uses it), backup video ready.

---

## 9. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Call says "an application error has occurred" | Webhook URL wrong, server down, or exception | Twilio Console > Monitor > Logs > Errors; check `PUBLIC_URL`, ngrok running, server logs |
| Twilio error 13331 | `language` not valid for the speech model | Try `bn-IN`, or set a `speechModel` that supports Bengali (see Twilio `<Gather>` docs) |
| Error 11200 / timeout | Reply took too long (about 15 s limit) | Voice fast mode, cache, async answer (D2-A2) |
| Call-back never rings | Number not verified (trial) or Bangladesh not enabled in Geo permissions | Verify number; enable Bangladesh |
| The number is "not found": missing under Phone Numbers > Active numbers, the API lists no numbers, nowhere to set "A call comes in" | The trial number is a shared Twilio-owned number, not owned by the account (the account ID and token are fine; calls from it still work) | Set the incoming-call webhook in Console > Try out Voice > Receive a call > Custom > Webhook URL `https://<ngrok-url>/voice/incoming` (POST) > Save. One webhook at a time; callers must be verified numbers; a trial message plays first; calls last at most 10 minutes. Outbound calls ("Call me") use `TWILIO_NUMBER` as the From number as usual |
| Nobody can call the number | On a trial only verified numbers can call in | Console > Verified recipients: add each teammate's phone (about 5 allowed), or upgrade the account |
| `SpeechResult` empty or wrong | Noise, dialect, too short | Speak clearly near the phone; agent repeats what it heard on low confidence |
| Gemini 429 / quota | Free tier limit | Key rotation, cache, fast model for grading/verify, fewer eval runs, `LLM_BACKEND=hybrid` |
| `LLMUnavailable` with Ollama, "connection refused" | Ollama is not running | Start the Ollama app (or `ollama serve`); check `OLLAMA_URL` |
| First Ollama answer takes 10 s or more | Model is loading into memory | Normal once; keep `keep_alive` set, warm it up with one request at startup |
| Voice answers too slow with Ollama | A full answer is about 700 Bangla tokens | Keep MAIN on Gemini (`hybrid`), or rely on the async voice answer (D2-A2) |
| textbee SMS not delivered | Phone offline, battery saver, no SMS balance | Keep app open, disable battery optimisation, top up |
| Bangla shows as `???` | Encoding | Use Swagger, UTF-8 files, `ensure_ascii=False` in JSON dumps |
| BanglaBERT predictions poor | Text not normalised the same way as training | Use the csebuetnlp normaliser in both training and inference |
| ngrok URL changed | Restarted free tunnel | Use the static domain or update `PUBLIC_URL` + Twilio webhook |
| Calls reach a teammate's laptop instead of yours | The Twilio number's webhook points to another ngrok URL | One webhook at a time: update "A call comes in" and `PUBLIC_URL` when the voice laptop changes |
| Every Twilio webhook gets 403 | Signature check uses a different URL than Twilio called (old ngrok URL, missing query string) | Validate against `PUBLIC_URL` + path + query string; restart after changing `PUBLIC_URL` |

---

## 10. Definition of Done (project)
- [ ] All MUST requirements in `SRS.md` pass their acceptance checks.
- [ ] Scenarios S1 to S9 recorded in `docs/results/scenario_check.md`.
- [ ] `ruff check .` and `pytest -q` pass; architecture test green.
- [ ] `docs/results/router_eval.md` and `rag_eval.md` exist with real numbers.
- [ ] README lets a new person run the project in 15 minutes.
- [ ] Backup video recorded; repo, models and vector store copied to USB.
