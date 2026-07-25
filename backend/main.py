from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from backend.api import auth, chat, documents
from backend.api.deps import get_store
from backend.config import get_settings
from backend.seed import DEMO_EMAIL, DEMO_PASSWORD, seed_demo_user

settings = get_settings()
settings.upload_dir.mkdir(parents=True, exist_ok=True)
settings.vector_store_path.parent.mkdir(parents=True, exist_ok=True)

API_DESCRIPTION = """
AI PDF Chat API — RAG chat over uploaded PDFs.

### Quick start
1. `POST /api/auth/login` with the demo user  
2. `POST /api/documents/upload` with a PDF  
3. `POST /api/chat` with your question  

### Demo credentials
- Email: `{email}`
- Password: `{password}`
""".format(email=DEMO_EMAIL, password=DEMO_PASSWORD)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    store = get_store(settings)
    user = seed_demo_user(store)
    print(f"Seeded demo user: {DEMO_EMAIL} (id={user.id})")
    yield


app = FastAPI(
    title="AI PDF Chat API",
    version="1.0.0",
    description=API_DESCRIPTION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {"name": "auth", "description": "Register, login, and session identity"},
        {"name": "documents", "description": "PDF upload, listing, and deletion"},
        {"name": "chat", "description": "RAG question answering over documents"},
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(chat.router)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "ai-pdf-chat"}


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def root() -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>AI PDF Chat API</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700&display=swap" rel="stylesheet" />
  <style>
    :root {{
      --bg: #0f4c5c;
      --ink: #f4fffd;
      --muted: rgba(244,255,253,.72);
      --panel: rgba(255,255,255,.08);
      --line: rgba(255,255,255,.14);
      --accent: #5eead4;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0; min-height: 100vh; font-family: "Plus Jakarta Sans", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(700px 360px at 90% 10%, rgba(94,234,212,.25), transparent 60%),
        linear-gradient(155deg, #0b3b3a 0%, #0f4c5c 50%, #16324f 100%);
      display: grid; place-items: center; padding: 2rem;
    }}
    .card {{
      width: min(560px, 100%);
      padding: 2rem;
      border: 1px solid var(--line);
      border-radius: 18px;
      background: var(--panel);
      backdrop-filter: blur(10px);
      box-shadow: 0 24px 60px rgba(0,0,0,.25);
    }}
    .mark {{
      width: 42px; height: 42px; border-radius: 12px; display: grid; place-items: center;
      background: linear-gradient(145deg, #0b6e6a, #155e75); font-weight: 700; font-size: .8rem;
    }}
    h1 {{ margin: .9rem 0 .4rem; letter-spacing: -.03em; font-size: 1.8rem; }}
    p {{ margin: 0; color: var(--muted); line-height: 1.5; }}
    .creds, .links {{ margin-top: 1.2rem; display: grid; gap: .55rem; }}
    code {{
      display: inline-block; padding: .2rem .45rem; border-radius: 6px;
      background: rgba(0,0,0,.25); color: var(--accent); font-size: .85rem;
    }}
    a {{
      color: var(--ink); text-decoration: none; font-weight: 600;
      border: 1px solid var(--line); border-radius: 10px; padding: .7rem .9rem;
      background: rgba(255,255,255,.06);
    }}
    a:hover {{ border-color: var(--accent); }}
  </style>
</head>
<body>
  <main class="card">
    <div class="mark">AI</div>
    <h1>AI PDF Chat API</h1>
    <p>Talk to your PDF — backend for upload, embeddings, and RAG chat. Use the interactive docs to try endpoints.</p>
    <div class="creds">
      <div>Demo login: <code>{DEMO_EMAIL}</code> / <code>{DEMO_PASSWORD}</code></div>
      <div>Health: <code>/health</code></div>
    </div>
    <div class="links">
      <a href="/docs">Open Swagger docs →</a>
      <a href="/redoc">Open ReDoc →</a>
      <a href="http://localhost:5173">Open frontend app →</a>
    </div>
  </main>
</body>
</html>"""
