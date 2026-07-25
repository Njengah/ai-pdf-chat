# AI PDF Chat

Chat with uploaded PDFs using retrieval-augmented generation (RAG).

## Stack

- **Backend:** FastAPI, pypdf, OpenAI-compatible / Anthropic LLM (PR2+)
- **Frontend:** Vite + React + TypeScript
- **Storage:** SQLite (`data/app.db`) + local PDF uploads

## PR roadmap

1. **PR1:** SQLite + Settings shell  
2. **PR2:** Models CRUD (OpenAI + Anthropic, server-side keys)  
3. **PR3:** Chat switcher + history + export  
4. **PR4 (current):** Streaming + RAG steps  
5. **PR5:** Multi-upload + PDF viewer  
6. **PR6:** Theme + danger zone polish

## Layout

```
backend/
  api/         # HTTP routes (auth, documents, chat)
  services/    # PDF parse, embeddings, RAG chat engine
  models/      # Pydantic schemas + domain models
frontend/src/  # React UI
tests/         # Pytest suite
```

## Quick start

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env   # set OPENAI_API_KEY (or compatible)

uvicorn backend.main:app --reload --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

## API

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/auth/register` | Create user |
| POST | `/api/auth/login` | Get JWT |
| POST | `/api/documents/upload` | Upload PDF |
| GET | `/api/documents` | List documents |
| DELETE | `/api/documents/{id}` | Remove document |
| POST | `/api/chat` | Ask a question over docs (optional `model_id`) |
| POST | `/api/chat/stream` | SSE stream: stages + tokens + sources |
| GET | `/api/chat/sessions` | List chat history |
| PATCH/DELETE | `/api/chat/sessions/{id}` | Rename / delete chat |
| GET | `/api/chat/sessions/{id}/export` | Export chat as Markdown |
| GET | `/api/chat/{session_id}` | Fetch full session |
| GET | `/api/settings/status` | Settings shell / storage info |
| GET/POST | `/api/models` | List / create LLM models |
| PATCH/DELETE | `/api/models/{id}` | Update / delete model |
| POST | `/api/models/{id}/default` | Set default chat/embedding model |

## Agent rules

1. Keep RAG pipeline in `backend/services/` — do not put chunking/LLM logic in routers.
2. Prefer typed Pydantic models in `backend/models/`.
3. Frontend talks only to `/api/*`; never call OpenAI from the browser.
4. Add or update tests under `tests/` for new endpoints and services.
5. Do not commit `.env`, uploaded PDFs, or vector store dumps.

## Test

```bash
pytest tests/ -q
```
