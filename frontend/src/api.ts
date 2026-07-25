const TOKEN_KEY = "ai_pdf_chat_token";

export type DocumentMeta = {
  id: string;
  filename: string;
  page_count: number;
  chunk_count: number;
  uploaded_at: string;
};

export type SourceChunk = {
  document_id: string;
  filename: string;
  page: number;
  text: string;
  score: number;
};

export type ChatMessage = {
  role: string;
  content: string;
  sources?: SourceChunk[];
  created_at: string;
};

export type ChatResponse = {
  session_id: string;
  answer: string;
  sources: SourceChunk[];
  messages: ChatMessage[];
};

function authHeaders(): HeadersInit {
  const token = localStorage.getItem(TOKEN_KEY);
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function parseError(res: Response): Promise<string> {
  try {
    const data = await res.json();
    return typeof data.detail === "string" ? data.detail : res.statusText;
  } catch {
    return res.statusText;
  }
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export async function register(email: string, password: string): Promise<void> {
  const res = await fetch("/api/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  const data = await res.json();
  setToken(data.access_token);
}

export async function login(email: string, password: string): Promise<void> {
  const res = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  const data = await res.json();
  setToken(data.access_token);
}

export async function listDocuments(): Promise<DocumentMeta[]> {
  const res = await fetch("/api/documents", { headers: authHeaders() });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function uploadDocument(file: File): Promise<DocumentMeta> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch("/api/documents/upload", {
    method: "POST",
    headers: authHeaders(),
    body: form,
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function deleteDocument(id: string): Promise<void> {
  const res = await fetch(`/api/documents/${id}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await parseError(res));
}

export async function askChat(
  question: string,
  sessionId?: string | null,
  documentIds?: string[]
): Promise<ChatResponse> {
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({
      question,
      session_id: sessionId || null,
      document_ids: documentIds?.length ? documentIds : null,
    }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}
