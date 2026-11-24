# Ek Call: First-time setup

For every team member, once per laptop. It takes about 30 to 45 minutes, mostly downloads, so use good Wi-Fi. Commands are for Windows PowerShell; Linux and macOS versions are given where they differ.

When you finish, you have: the API running at `http://localhost:8000`, the app at `http://localhost:5173`, and all tests green. That is **Sync 0** in `docs/BUILD_PLAN.md`.

---

## 1. Install the tools

| Tool | Version | Check |
|---|---|---|
| Python | **3.11** exactly (the pinned packages do not install on 3.12+). On Windows tick "Add python.exe to PATH". | `py -3.11 --version` |
| Node.js | 22 LTS (20.19 or newer also works) | `node --version` |
| Git | any recent | `git --version` |
| VS Code, Chrome | latest | the app's mic needs Chrome |
| Ollama (optional) | latest, then `ollama pull qwen2.5:7b` (about 5 GB, needs 8 GB RAM or more) | `ollama list` |

Ollama is optional: it is a free local LLM, so you can test without Gemini keys.

## 2. Get the code

```powershell
git clone <TEAM_REPO_URL> ek-call
cd ek-call
```

## 3. Backend: Python environment

```powershell
cd backend
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install torch==2.15.0 --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
pip install git+https://github.com/csebuetnlp/normalizer
```

- Linux / macOS: `python3.11 -m venv .venv` and `source .venv/bin/activate`, the rest is the same.
- If PowerShell refuses to run `Activate.ps1`: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, then try again.
- Every new terminal for the backend: `cd backend` and `.venv\Scripts\Activate.ps1` first.

## 4. Backend: your `.env`

```powershell
copy .env.example .env        # Linux / macOS: cp .env.example .env
```

Open `backend/.env` and fill in:

| Variable | What to put |
|---|---|
| `PHONE_HASH_SALT`, `ADMIN_TOKEN` | Two different random strings: run `python -c "import secrets; print(secrets.token_urlsafe(32))"` twice. |
| `LLM_BACKEND` | `ollama` if you installed Ollama (no keys needed), otherwise `gemini`. |
| `GEMINI_API_KEYS` | Your Gemini key from Google AI Studio (comma separated if you have several). Tamim shares the team keys privately. |
| `GEMINI_MODEL_MAIN`, `GEMINI_MODEL_FAST` | The model names Tamim sends (today both are `gemini-3.5-flash-lite`: the Flash models answer too slowly for a call). |
| `GEMINI_MODEL_FALLBACK` | `gemini-3.1-flash-lite`: used once when the model above is overloaded ("high demand", HTTP 503) or out of quota. |
| `AGENT_ENGINE` | `langgraph` = the real agent (needs a working LLM). `stub` = a fixed sample answer, no keys or models needed: handy while you build the app or the call flow. |
| `PRELOAD_MODELS` | `true` = load the router and search models in the background when the server starts, so the first question is fast. `false` = load them on the first question. |
| Ragib | `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_NUMBER` (from Tamim), `PUBLIC_URL` (your ngrok URL). |
| Ariful | `SMS_BACKEND=textbee`, `TEXTBEE_API_KEY`, `TEXTBEE_DEVICE_ID` once the textbee phone works; until then keep `SMS_BACKEND=console`. |

**Write each value right after the `=`.** Everything after a `#` is a comment, so a line like `GEMINI_API_KEYS=      # key1,key2` is read as **empty**. Delete the comment or put the value before it.

Never commit `.env` and never paste keys in a group chat that keeps history. `.env` is git-ignored.

## 5. Backend: search model and index (once)

```powershell
$env:PYTHONIOENCODING = "utf-8"           # so Bangla prints correctly in PowerShell
python -m scripts.check_docs
python -m scripts.ingest
python -m scripts.search "বয়স্ক ভাতার বয়স কত"
python -m scripts.train_baseline
python -m scripts.ask "আমার বয়স ৬৭, বয়স্ক ভাতা পাবো?"
```

- `check_docs` may end with "not ready yet" because 3 birth registration links are still being collected. That is known and fine.
- The first `ingest` downloads the e5 search model (about 470 MB) into `backend/data/models/e5`, then builds the index in `backend/data/chroma` (about 97 passages). Both folders are git-ignored.
- The search should list an old-age allowance passage first.
- `train_baseline` trains the TF-IDF router from `data/questions/train.csv` in a few seconds and saves `backend/data/models/tfidf_router.joblib` (git-ignored).
- The better router is BanglaBERT (`ROUTER_BACKEND=banglabert`), but its model folder (about 450 MB) is not in git. Without it the app quietly uses TF-IDF, which is fine for development. To use it, get the zipped `router` folder from Tamim's Google Drive and unzip it to `backend/data/models/router/` (or train it yourself: `ml/README.md`). `/health` shows which router is in use.
- `ask` runs the real agent once and prints the service, the Bangla answer, the checklist and the sources. It needs a working LLM; the first question takes 15 to 35 s because the models load, later ones about 3 to 5 s.
- Before a demo or rehearsal: `python -m scripts.prewarm` asks the questions in `data/questions/demo_questions.txt` once and stores the answers for 24 hours; repeating them then takes well under a second and uses no Gemini quota.
- If `ingest` says it "couldn't connect to huggingface.co" although your internet works, the variable `HF_HUB_OFFLINE` is set on your computer. In that terminal run `Remove-Item Env:HF_HUB_OFFLINE` (Linux / macOS: `unset HF_HUB_OFFLINE`) and run `ingest` again.

## 6. Backend: check that everything works

```powershell
ruff check .
pytest -q
python -m scripts.llm_smoke                 # one Bangla JSON answer (needs Ollama or a Gemini key)
uvicorn app.main:app --reload --port 8000
```

- `ruff` says "All checks passed!" and `pytest` shows all tests passing.
- Open `http://localhost:8000/docs` (Swagger). Try `GET /health`: `db` and `vector_db` should be `ok`; `llm` is `ok` (or `not_configured` if you have no Gemini key and use `LLM_BACKEND=gemini`).
- Try `POST /api/v1/chat` with `{"phone": "01712345678", "message": "বয়স্ক ভাতা"}`. Until the agent is merged (Checkpoint 1), you get a fixed sample answer from the stub engine.
- Test Bangla requests in Swagger, not with `curl` in PowerShell (encoding problems).

## 7. Frontend

In a second terminal:

```powershell
cd frontend
npm install
npm run dev          # opens http://localhost:5173
npm run build        # must pass before every pull request with frontend changes
```

After step D1-R3 there is a `frontend/.env.example`: copy it to `frontend/.env`.

## 8. Extra setup by role

| Who | What |
|---|---|
| Tamim | Ollama with `qwen2.5:7b`; Google Colab for BanglaBERT training (D1-T6); collects the 3 Gemini keys; owns the Twilio trial account and verifies Ragib's and Ariful's phone numbers on it. |
| Ragib | ngrok: install, `ngrok config add-authtoken <your token>`, then `ngrok http 8000` (or `ngrok http --url=<static domain> 8000`). Put the https URL in `PUBLIC_URL` and in the Twilio number's "A call comes in" webhook (`docs/BUILD_PLAN.md`, D1-A3). |
| Ariful | textbee: Android phone with a Bangladeshi SIM and SMS balance, textbee app installed and registered; API key and device ID in `.env`. |

## 9. Every day

```powershell
git checkout main
git pull
git checkout -b <your-name>/<step>-<short-name>      # for example ragib/d1-a3-voice-echo
```

| If this changed in `main` | Run |
|---|---|
| `backend/requirements.txt` | `pip install -r requirements.txt` (venv active) |
| `frontend/package.json` | `npm install` |
| `backend/data/raw_docs/` | `python -m scripts.ingest` |
| `backend/data/questions/train.csv` | `python -m scripts.train_baseline` |
| `backend/.env.example` | copy the new variables into your `.env` |

Before opening a pull request: `git pull origin main` into your branch, then `ruff check .`, `pytest -q` and (frontend) `npm run build`. Rules: `docs/BUILD_PLAN.md` Section 0.3.

## 10. Troubleshooting

| Problem | Fix |
|---|---|
| `py -3.11` not found | Install Python 3.11 from python.org with "Add to PATH" ticked; reopen the terminal. |
| `pip install` fails on `torch` or `chromadb` | The venv is not active or it is not Python 3.11 (`python --version` inside the venv). |
| Bangla shows as `???` | `$env:PYTHONIOENCODING = "utf-8"`; use Swagger for requests; save files as UTF-8. |
| Port 8000 already in use | Stop the other server, or use `--port 8001` and change `VITE_API_URL` in `frontend/.env`. |
| Browser shows a CORS error | `FRONTEND_ORIGINS` in `backend/.env` must include `http://localhost:5173`. |
| `llm` is `error` in `/health` with Ollama | Start the Ollama app (or `ollama serve`) and check `ollama list` shows `qwen2.5:7b`. |
| First Ollama answer takes about 10 s | Normal: the model is loading into memory; later answers take about 1 s. |
