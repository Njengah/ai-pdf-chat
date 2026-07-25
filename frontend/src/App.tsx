import { FormEvent, useEffect, useRef, useState } from "react";
import {
  ChatMessage,
  DocumentMeta,
  askChat,
  deleteDocument,
  getToken,
  listDocuments,
  login,
  register,
  setToken,
  uploadDocument,
} from "./api";
import Settings from "./Settings";

const PROMPTS = [
  "Summarize this document in 5 bullets",
  "What are the key findings?",
  "List important dates and numbers",
];

export default function App() {
  const [authed, setAuthed] = useState(Boolean(getToken()));
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("demo@example.com");
  const [password, setPassword] = useState("demo1234");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [docs, setDocs] = useState<DocumentMeta[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [question, setQuestion] = useState("");
  const [page, setPage] = useState<"chat" | "settings">("chat");
  const bottomRef = useRef<HTMLDivElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  async function refreshDocs() {
    const items = await listDocuments();
    setDocs(items);
  }

  useEffect(() => {
    if (!authed) return;
    refreshDocs().catch((err) => setError(err.message));
  }, [authed]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  async function onAuth(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (mode === "login") await login(email, password);
      else await register(email, password);
      setAuthed(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Auth failed");
    } finally {
      setBusy(false);
    }
  }

  async function onUpload(file: File | undefined) {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      await uploadDocument(file);
      await refreshDocs();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  async function onDelete(id: string) {
    setBusy(true);
    setError(null);
    try {
      await deleteDocument(id);
      setSelected((prev) => prev.filter((x) => x !== id));
      await refreshDocs();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setBusy(false);
    }
  }

  async function sendQuestion(text: string) {
    const q = text.trim();
    if (!q || busy) return;
    setBusy(true);
    setError(null);
    setQuestion("");
    try {
      const res = await askChat(q, sessionId, selected);
      setSessionId(res.session_id);
      setMessages(res.messages);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Chat failed");
    } finally {
      setBusy(false);
    }
  }

  async function onAsk(e: FormEvent) {
    e.preventDefault();
    await sendQuestion(question);
  }

  function toggleDoc(id: string) {
    setSelected((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  }

  function newChat() {
    setMessages([]);
    setSessionId(null);
    setError(null);
    setQuestion("");
  }

  if (!authed) {
    return (
      <div className="auth-shell">
        <div className="auth-visual" aria-hidden="true">
          <div className="auth-orb" />
          <div className="auth-grid" />
          <div className="auth-copy">
            <span className="logo-mark">AI</span>
            <p className="brand">AI PDF Chat</p>
            <h1>Chat with your PDFs like a real workspace.</h1>
            <p className="lede">
              Upload contracts, papers, or manuals — ask questions and get answers with page citations.
            </p>
          </div>
        </div>

        <div className="auth-panel">
          <div className="auth-panel-head">
            <p className="eyebrow">{mode === "login" ? "Sign in" : "Create account"}</p>
            <h2>{mode === "login" ? "Continue to AI PDF Chat" : "Get started"}</h2>
          </div>

          <form onSubmit={onAuth} className="stack">
            <label>
              Email
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="email"
                required
              />
            </label>
            <label>
              Password
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete={mode === "login" ? "current-password" : "new-password"}
                required
                minLength={6}
              />
            </label>
            {error && <p className="error">{error}</p>}
            <button type="submit" className="btn-primary" disabled={busy}>
              {busy ? "Working…" : mode === "login" ? "Sign in" : "Create account"}
            </button>
          </form>

          <button
            type="button"
            className="btn-text"
            onClick={() => {
              setMode(mode === "login" ? "register" : "login");
              setError(null);
            }}
          >
            {mode === "login" ? "Need an account? Register" : "Have an account? Sign in"}
          </button>
        </div>
      </div>
    );
  }

  if (page === "settings") {
    return <Settings onBack={() => setPage("chat")} />;
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <span className="logo-mark sm">AI</span>
          <div>
            <p className="brand">AI PDF Chat</p>
            <small>Talk to your PDF</small>
          </div>
        </div>

        <button type="button" className="btn-secondary" onClick={newChat}>
          New chat
        </button>
        <button type="button" className="btn-text settings-link" onClick={() => setPage("settings")}>
          Settings
        </button>

        <div className="sidebar-section">
          <div className="section-head">
            <h3>Library</h3>
            <button
              type="button"
              className="btn-text sm"
              onClick={() => fileRef.current?.click()}
              disabled={busy}
            >
              Upload
            </button>
            <input
              ref={fileRef}
              type="file"
              accept="application/pdf"
              hidden
              onChange={(e) => onUpload(e.target.files?.[0])}
            />
          </div>

          <ul className="doc-list">
            {docs.map((doc) => {
              const active = selected.includes(doc.id);
              return (
                <li key={doc.id} className={active ? "active" : ""}>
                  <button
                    type="button"
                    className="doc-main"
                    onClick={() => toggleDoc(doc.id)}
                    title="Toggle document scope"
                  >
                    <span className="doc-icon">PDF</span>
                    <span className="doc-meta">
                      <strong>{doc.filename}</strong>
                      <small>
                        {doc.page_count} pages · {doc.chunk_count} chunks
                        {active ? " · scoped" : ""}
                      </small>
                    </span>
                  </button>
                  <button
                    type="button"
                    className="btn-icon"
                    aria-label={`Remove ${doc.filename}`}
                    onClick={() => onDelete(doc.id)}
                  >
                    ×
                  </button>
                </li>
              );
            })}
            {docs.length === 0 && (
              <li className="empty-docs">
                Drop a PDF via Upload to start chatting.
              </li>
            )}
          </ul>
        </div>

        <div className="sidebar-foot">
          <p className="scope-note">
            {selected.length
              ? `Scoped to ${selected.length} file${selected.length > 1 ? "s" : ""}`
              : "Searching all documents"}
          </p>
          <button
            type="button"
            className="btn-text"
            onClick={() => {
              setToken(null);
              setAuthed(false);
              newChat();
            }}
          >
            Sign out
          </button>
        </div>
      </aside>

      <main className="chat">
        <header className="chat-top">
          <div>
            <h1>Workspace chat</h1>
            <p>
              Answers cite pages from your library
              {sessionId ? " · session active" : ""}
            </p>
          </div>
          <div className="status-pill">{busy ? "Thinking" : "Ready"}</div>
        </header>

        <div className="messages">
          {messages.length === 0 && !busy && (
            <div className="empty-state">
              <span className="logo-mark">AI</span>
              <h2>Ask anything about your PDFs</h2>
              <p>Pick a prompt or type your own question below.</p>
              <div className="prompt-row">
                {PROMPTS.map((p) => (
                  <button
                    key={p}
                    type="button"
                    className="prompt-chip"
                    onClick={() => sendQuestion(p)}
                    disabled={busy || docs.length === 0}
                  >
                    {p}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg, idx) => (
            <article key={`${msg.role}-${idx}`} className={`msg ${msg.role}`}>
              <div className="msg-avatar" aria-hidden="true">
                {msg.role === "user" ? "You" : "AI"}
              </div>
              <div className="msg-body">
                <p>{msg.content}</p>
                {msg.sources && msg.sources.length > 0 && (
                  <details className="sources">
                    <summary>{msg.sources.length} sources</summary>
                    <ul>
                      {msg.sources.map((src, i) => (
                        <li key={`${src.document_id}-${i}`}>
                          <div className="source-top">
                            <strong>{src.filename}</strong>
                            <span>p.{src.page}</span>
                          </div>
                          <p>{src.text.slice(0, 200)}…</p>
                        </li>
                      ))}
                    </ul>
                  </details>
                )}
              </div>
            </article>
          ))}

          {busy && (
            <article className="msg assistant typing">
              <div className="msg-avatar" aria-hidden="true">
                AI
              </div>
              <div className="msg-body">
                <div className="dots" aria-label="Thinking">
                  <span />
                  <span />
                  <span />
                </div>
              </div>
            </article>
          )}
          <div ref={bottomRef} />
        </div>

        {error && <p className="error banner">{error}</p>}

        <form className="composer" onSubmit={onAsk}>
          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                void sendQuestion(question);
              }
            }}
            placeholder="Ask about your documents…"
            rows={1}
            disabled={busy}
          />
          <button
            type="submit"
            className="btn-primary send"
            disabled={busy || !question.trim()}
          >
            Send
          </button>
        </form>
      </main>
    </div>
  );
}
