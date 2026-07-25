import { FormEvent, useEffect, useRef, useState } from "react";
import {
  ChatMessage,
  ChatSessionSummary,
  DocumentMeta,
  LLMModel,
  SourceChunk,
  askChatStream,
  deleteDocument,
  deleteSession,
  exportSessionMarkdown,
  getSession,
  getToken,
  listDocuments,
  listModels,
  listSessions,
  login,
  register,
  renameSession,
  setToken,
  uploadDocumentWithProgress,
} from "./api";
import PdfViewer from "./PdfViewer";
import Settings from "./Settings";
import ToastStack, { ToastMessage } from "./Toast";

type UploadItem = {
  id: string;
  name: string;
  percent: number;
  status: "uploading" | "done" | "error";
  error?: string;
};

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
  const [sessionTitle, setSessionTitle] = useState("New chat");
  const [sessions, setSessions] = useState<ChatSessionSummary[]>([]);
  const [chatModels, setChatModels] = useState<LLMModel[]>([]);
  const [modelId, setModelId] = useState<string>("");
  const [question, setQuestion] = useState("");
  const [page, setPage] = useState<"chat" | "settings">("chat");
  const [stage, setStage] = useState<string | null>(null);
  const [streamSources, setStreamSources] = useState<SourceChunk[]>([]);
  const [uploads, setUploads] = useState<UploadItem[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const [viewer, setViewer] = useState<{
    documentId: string;
    filename: string;
    page: number;
  } | null>(null);
  const [booting, setBooting] = useState(false);
  const [toasts, setToasts] = useState<ToastMessage[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  function pushToast(text: string, tone: "ok" | "error" = "ok") {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    setToasts((prev) => [...prev, { id, text, tone }]);
  }

  async function refreshDocs() {
    setDocs(await listDocuments());
  }

  async function refreshSessions() {
    setSessions(await listSessions());
  }

  async function refreshModels() {
    const models = await listModels("chat");
    setChatModels(models);
    setModelId((prev) => {
      if (prev && models.some((m) => m.id === prev)) return prev;
      const def = models.find((m) => m.is_default);
      return def?.id || models[0]?.id || "";
    });
  }

  useEffect(() => {
    if (!authed) return;
    setBooting(true);
    Promise.all([refreshDocs(), refreshSessions(), refreshModels()])
      .catch((err) => {
        setError(err.message);
        pushToast(err.message, "error");
      })
      .finally(() => setBooting(false));
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
      pushToast(mode === "login" ? "Signed in" : "Account created");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Auth failed";
      setError(message);
      pushToast(message, "error");
    } finally {
      setBusy(false);
    }
  }

  async function uploadOne(file: File) {
    const id = `${file.name}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    setUploads((prev) => [
      ...prev,
      { id, name: file.name, percent: 0, status: "uploading" },
    ]);
    try {
      await uploadDocumentWithProgress(file, (percent) => {
        setUploads((prev) =>
          prev.map((item) => (item.id === id ? { ...item, percent } : item))
        );
      });
      setUploads((prev) =>
        prev.map((item) =>
          item.id === id ? { ...item, percent: 100, status: "done" } : item
        )
      );
    } catch (err) {
      const message = err instanceof Error ? err.message : "Upload failed";
      setUploads((prev) =>
        prev.map((item) =>
          item.id === id ? { ...item, status: "error", error: message } : item
        )
      );
      throw err;
    }
  }

  async function onUploadFiles(fileList: FileList | File[] | null | undefined) {
    if (!fileList) return;
    const files = Array.from(fileList).filter((f) =>
      f.name.toLowerCase().endsWith(".pdf")
    );
    if (!files.length) {
      setError("Only PDF files are supported");
      return;
    }
    setBusy(true);
    setError(null);
    const failures: string[] = [];
    for (const file of files) {
      try {
        await uploadOne(file);
      } catch (err) {
        failures.push(err instanceof Error ? err.message : file.name);
      }
    }
    await refreshDocs();
    setBusy(false);
    if (fileRef.current) fileRef.current.value = "";
    if (failures.length) {
      setError(`${failures.length} upload(s) failed`);
      pushToast(`${failures.length} upload(s) failed`, "error");
    } else {
      pushToast(`Uploaded ${files.length} PDF${files.length > 1 ? "s" : ""}`);
    }
    window.setTimeout(() => {
      setUploads((prev) => prev.filter((u) => u.status === "uploading"));
    }, 2500);
  }

  function openSource(src: SourceChunk) {
    setViewer({
      documentId: src.document_id,
      filename: src.filename,
      page: src.page || 1,
    });
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
    setStage("Retrieving passages");
    setStreamSources([]);

    const userMsg: ChatMessage = {
      role: "user",
      content: q,
      created_at: new Date().toISOString(),
    };
    const assistantMsg: ChatMessage = {
      role: "assistant",
      content: "",
      sources: [],
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg, assistantMsg]);

    try {
      await askChatStream(q, sessionId, selected, modelId || null, {
        onStage: (_stage, label) => setStage(label),
        onToken: (token) => {
          setMessages((prev) => {
            const next = [...prev];
            const last = next[next.length - 1];
            if (!last || last.role !== "assistant") return prev;
            next[next.length - 1] = { ...last, content: last.content + token };
            return next;
          });
        },
        onSources: (sources) => {
          setStreamSources(sources);
          setMessages((prev) => {
            const next = [...prev];
            const last = next[next.length - 1];
            if (!last || last.role !== "assistant") return prev;
            next[next.length - 1] = { ...last, sources };
            return next;
          });
        },
        onDone: (payload) => {
          setSessionId(payload.session_id);
          setSessionTitle(payload.title || "New chat");
          if (payload.model_id) setModelId(payload.model_id);
          setMessages(payload.messages);
          setStage(null);
        },
      });
      await refreshSessions();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Chat failed");
      setMessages((prev) => {
        // Drop empty trailing assistant bubble on failure
        if (prev.length && prev[prev.length - 1]?.role === "assistant" && !prev[prev.length - 1].content) {
          return prev.slice(0, -1);
        }
        return prev;
      });
    } finally {
      setBusy(false);
      setStage(null);
      setStreamSources([]);
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

  function chatWithDoc(id: string) {
    setSelected([id]);
    setMessages([]);
    setSessionId(null);
    setSessionTitle("New chat");
    setError(null);
    setQuestion("");
  }

  function newChat() {
    setMessages([]);
    setSessionId(null);
    setSessionTitle("New chat");
    setError(null);
    setQuestion("");
  }

  async function openSession(id: string) {
    setBusy(true);
    setError(null);
    try {
      const session = await getSession(id);
      setSessionId(session.id);
      setSessionTitle(session.title);
      setMessages(session.messages);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to open chat");
    } finally {
      setBusy(false);
    }
  }

  async function onRenameSession(id: string, current: string) {
    const next = window.prompt("Rename chat", current);
    if (!next || !next.trim()) return;
    try {
      await renameSession(id, next.trim());
      await refreshSessions();
      if (sessionId === id) setSessionTitle(next.trim());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Rename failed");
    }
  }

  async function onDeleteSession(id: string) {
    if (!confirm("Delete this chat?")) return;
    try {
      await deleteSession(id);
      if (sessionId === id) newChat();
      await refreshSessions();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    }
  }

  async function onExport() {
    if (!sessionId) return;
    try {
      const md = await exportSessionMarkdown(sessionId);
      const blob = new Blob([md], { type: "text/markdown;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${sessionTitle.replace(/[^\w\-]+/g, "_").slice(0, 40) || "chat"}.md`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export failed");
    }
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
    return (
      <>
        <Settings
          onBack={() => {
            setPage("chat");
            refreshModels().catch(() => undefined);
            refreshDocs().catch(() => undefined);
            refreshSessions().catch(() => undefined);
          }}
          onWorkspaceCleared={() => {
            newChat();
            setDocs([]);
            setSessions([]);
            setSelected([]);
            setViewer(null);
          }}
          pushToast={pushToast}
        />
        <ToastStack
          toasts={toasts}
          onDismiss={(id) => setToasts((prev) => prev.filter((t) => t.id !== id))}
        />
      </>
    );
  }

  return (
    <div className={`app-shell ${viewer ? "with-viewer" : ""}`}>
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
            <h3>Chats</h3>
          </div>
          <ul className="session-list">
            {booting &&
              [0, 1, 2].map((i) => (
                <li key={`sk-s-${i}`} className="skeleton-card">
                  <div className="skeleton line" />
                  <div className="skeleton line short" />
                </li>
              ))}
            {!booting &&
              sessions.map((s) => (
                <li key={s.id} className={sessionId === s.id ? "active" : ""}>
                  <button type="button" className="session-main" onClick={() => openSession(s.id)}>
                    <strong>{s.title}</strong>
                    <small>
                      {s.message_count} msgs
                      {s.preview ? ` · ${s.preview.slice(0, 40)}` : ""}
                    </small>
                  </button>
                  <div className="session-actions">
                    <button
                      type="button"
                      className="btn-icon"
                      title="Rename"
                      onClick={() => onRenameSession(s.id, s.title)}
                    >
                      ✎
                    </button>
                    <button
                      type="button"
                      className="btn-icon"
                      title="Delete"
                      onClick={() => onDeleteSession(s.id)}
                    >
                      ×
                    </button>
                  </div>
                </li>
              ))}
            {!booting && sessions.length === 0 && (
              <li className="empty-docs">No chats yet. Ask something to start.</li>
            )}
          </ul>
        </div>

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
              multiple
              hidden
              onChange={(e) => onUploadFiles(e.target.files)}
            />
          </div>

          <div
            className={`dropzone ${dragOver ? "active" : ""}`}
            onDragEnter={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={(e) => {
              e.preventDefault();
              setDragOver(false);
            }}
            onDrop={(e) => {
              e.preventDefault();
              setDragOver(false);
              void onUploadFiles(e.dataTransfer.files);
            }}
          >
            Drop PDFs here or use Upload
          </div>

          {uploads.length > 0 && (
            <ul className="upload-list">
              {uploads.map((item) => (
                <li key={item.id} className={item.status}>
                  <div className="upload-row">
                    <strong>{item.name}</strong>
                    <small>
                      {item.status === "uploading" && `${item.percent}%`}
                      {item.status === "done" && "Done"}
                      {item.status === "error" && (item.error || "Failed")}
                    </small>
                  </div>
                  <div className="upload-bar">
                    <span style={{ width: `${item.percent}%` }} />
                  </div>
                </li>
              ))}
            </ul>
          )}

          <ul className="doc-list">
            {docs.map((doc) => {
              const active = selected.includes(doc.id);
              const viewing = viewer?.documentId === doc.id;
              return (
                <li key={doc.id} className={active || viewing ? "active" : ""}>
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
                  <div className="doc-actions">
                    <button
                      type="button"
                      className="btn-text sm"
                      onClick={() =>
                        setViewer({
                          documentId: doc.id,
                          filename: doc.filename,
                          page: 1,
                        })
                      }
                      title="Open PDF viewer"
                    >
                      View
                    </button>
                    <button
                      type="button"
                      className="btn-text sm"
                      onClick={() => chatWithDoc(doc.id)}
                      title="Chat with this PDF only"
                    >
                      Chat
                    </button>
                    <button
                      type="button"
                      className="btn-icon"
                      aria-label={`Remove ${doc.filename}`}
                      onClick={() => onDelete(doc.id)}
                    >
                      ×
                    </button>
                  </div>
                </li>
              );
            })}
            {docs.length === 0 && (
              <li className="empty-docs">Drop PDFs here to start chatting.</li>
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
            <h1>{sessionTitle}</h1>
            <p>
              Answers cite pages from your library
              {sessionId ? " · session active" : ""}
            </p>
          </div>
          <div className="chat-top-actions">
            <label className="model-switch">
              <span>Model</span>
              <select
                value={modelId}
                onChange={(e) => setModelId(e.target.value)}
                disabled={chatModels.length === 0}
              >
                {chatModels.length === 0 && <option value="">Local demo</option>}
                {chatModels.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name}
                    {m.is_default ? " (default)" : ""}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              className="btn-secondary export-btn"
              onClick={onExport}
              disabled={!sessionId || messages.length === 0}
            >
              Export MD
            </button>
            <div className="status-pill">{busy ? stage || "Thinking" : "Ready"}</div>
          </div>
        </header>

        {busy && stage && (
          <div className="rag-stages" aria-live="polite">
            {["Retrieving passages", "Ranking context", "Generating answer"].map((label) => {
              const active = stage === label;
              const done =
                (label === "Retrieving passages" &&
                  (stage === "Ranking context" || stage === "Generating answer")) ||
                (label === "Ranking context" && stage === "Generating answer");
              return (
                <span key={label} className={`rag-step ${active ? "active" : ""} ${done ? "done" : ""}`}>
                  {label}
                  {label === "Generating answer" && streamSources.length > 0
                    ? ` · ${streamSources.length} sources`
                    : ""}
                </span>
              );
            })}
          </div>
        )}

        <div className="messages">
          {messages.length === 0 && !busy && (
            <div className="empty-state">
              <span className="logo-mark">AI</span>
              <h2>Ask anything about your PDFs</h2>
              <p>Pick a prompt, choose a model, or start from a library PDF.</p>
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
                  <details className="sources" open={idx === messages.length - 1}>
                    <summary>{msg.sources.length} sources</summary>
                    <ul>
                      {msg.sources.map((src, i) => (
                        <li key={`${src.document_id}-${i}`}>
                          <button
                            type="button"
                            className="source-jump"
                            onClick={() => openSource(src)}
                            title="Open cited page"
                          >
                            <div className="source-top">
                              <strong>{src.filename}</strong>
                              <span>p.{src.page}</span>
                            </div>
                            <p>{src.text.slice(0, 200)}…</p>
                          </button>
                        </li>
                      ))}
                    </ul>
                  </details>
                )}
              </div>
            </article>
          ))}

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

      {viewer && (
        <PdfViewer
          documentId={viewer.documentId}
          filename={viewer.filename}
          page={viewer.page}
          onClose={() => setViewer(null)}
          onPageChange={(next) => setViewer((prev) => (prev ? { ...prev, page: next } : prev))}
        />
      )}

      <ToastStack
        toasts={toasts}
        onDismiss={(id) => setToasts((prev) => prev.filter((t) => t.id !== id))}
      />
    </div>
  );
}
