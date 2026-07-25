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
  title?: string;
  model_id?: string | null;
};

export type ChatSessionSummary = {
  id: string;
  owner_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  preview: string;
};

export type ChatSession = {
  id: string;
  owner_id: string;
  title: string;
  messages: ChatMessage[];
  created_at: string;
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
  return uploadDocumentWithProgress(file);
}

export function uploadDocumentWithProgress(
  file: File,
  onProgress?: (percent: number) => void
): Promise<DocumentMeta> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/documents/upload");
    const token = localStorage.getItem(TOKEN_KEY);
    if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);

    xhr.upload.onprogress = (event) => {
      if (!event.lengthComputable || !onProgress) return;
      onProgress(Math.round((event.loaded / event.total) * 100));
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText) as DocumentMeta);
        } catch {
          reject(new Error("Invalid upload response"));
        }
        return;
      }
      try {
        const data = JSON.parse(xhr.responseText);
        reject(new Error(typeof data.detail === "string" ? data.detail : xhr.statusText));
      } catch {
        reject(new Error(xhr.statusText || "Upload failed"));
      }
    };
    xhr.onerror = () => reject(new Error("Upload failed"));
    const form = new FormData();
    form.append("file", file);
    xhr.send(form);
  });
}

export async function fetchDocumentPdf(documentId: string): Promise<Blob> {
  const res = await fetch(`/api/documents/${documentId}/file`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.blob();
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
  documentIds?: string[],
  modelId?: string | null
): Promise<ChatResponse> {
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({
      question,
      session_id: sessionId || null,
      document_ids: documentIds?.length ? documentIds : null,
      model_id: modelId || null,
    }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export type StreamHandlers = {
  onStage?: (stage: string, label: string, sourceCount?: number) => void;
  onToken?: (text: string) => void;
  onSources?: (sources: SourceChunk[]) => void;
  onDone?: (payload: {
    session_id: string;
    title: string;
    model_id?: string | null;
    answer: string;
    messages: ChatMessage[];
  }) => void;
};

export async function askChatStream(
  question: string,
  sessionId: string | null | undefined,
  documentIds: string[] | undefined,
  modelId: string | null | undefined,
  handlers: StreamHandlers
): Promise<void> {
  const res = await fetch("/api/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({
      question,
      session_id: sessionId || null,
      document_ids: documentIds?.length ? documentIds : null,
      model_id: modelId || null,
    }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  if (!res.body) throw new Error("No stream body");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() || "";

    for (const part of parts) {
      const lines = part.split("\n");
      let event = "message";
      const dataLines: string[] = [];
      for (const line of lines) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
      }
      if (!dataLines.length) continue;
      const data = JSON.parse(dataLines.join("\n"));
      if (event === "stage") {
        handlers.onStage?.(data.stage, data.label, data.source_count);
      } else if (event === "token") {
        handlers.onToken?.(data.text || "");
      } else if (event === "sources") {
        handlers.onSources?.(data.sources || []);
      } else if (event === "done") {
        handlers.onDone?.(data);
      } else if (event === "error") {
        throw new Error(data.detail || "Stream failed");
      }
    }
  }
}

export async function listSessions(): Promise<ChatSessionSummary[]> {
  const res = await fetch("/api/chat/sessions", { headers: authHeaders() });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function getSession(id: string): Promise<ChatSession> {
  const res = await fetch(`/api/chat/${id}`, { headers: authHeaders() });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function renameSession(id: string, title: string): Promise<ChatSessionSummary> {
  const res = await fetch(`/api/chat/sessions/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ title }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function deleteSession(id: string): Promise<void> {
  const res = await fetch(`/api/chat/sessions/${id}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await parseError(res));
}

export async function exportSessionMarkdown(id: string): Promise<string> {
  const res = await fetch(`/api/chat/sessions/${id}/export`, { headers: authHeaders() });
  if (!res.ok) throw new Error(await parseError(res));
  return res.text();
}

export type SettingsStatus = {
  storage: string;
  database_path: string;
  upload_dir: string;
  sections: {
    models: { status: string; note: string };
    appearance: { status: string; note: string };
    danger: { status: string; note: string };
  };
  models?: {
    count: number;
    default_chat: string | null;
    default_embedding: string | null;
  };
  workspace?: {
    session_count: number;
    document_count: number;
  };
  demo: { connected: boolean };
};

export type LLMModel = {
  id: string;
  name: string;
  provider: "openai" | "anthropic" | string;
  model_id: string;
  kind: "chat" | "embedding" | string;
  base_url?: string | null;
  api_key_masked: string;
  has_api_key: boolean;
  is_default: boolean;
  created_at: string;
  updated_at: string;
};

export type LLMModelInput = {
  name: string;
  provider: "openai" | "anthropic";
  model_id: string;
  kind: "chat" | "embedding";
  base_url?: string;
  api_key?: string;
  is_default?: boolean;
};

export async function getSettingsStatus(): Promise<SettingsStatus> {
  const res = await fetch("/api/settings/status", { headers: authHeaders() });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function clearChats(): Promise<{ deleted_sessions: number }> {
  const res = await fetch("/api/settings/chats", {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function clearLibrary(): Promise<{ deleted_documents: number }> {
  const res = await fetch("/api/settings/library", {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function listModels(kind?: "chat" | "embedding"): Promise<LLMModel[]> {
  const qs = kind ? `?kind=${kind}` : "";
  const res = await fetch(`/api/models${qs}`, { headers: authHeaders() });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function createModel(body: LLMModelInput): Promise<LLMModel> {
  const res = await fetch("/api/models", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function updateModel(
  id: string,
  body: Partial<LLMModelInput>
): Promise<LLMModel> {
  const res = await fetch(`/api/models/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function setDefaultModel(id: string): Promise<LLMModel> {
  const res = await fetch(`/api/models/${id}/default`, {
    method: "POST",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function deleteModel(id: string): Promise<void> {
  const res = await fetch(`/api/models/${id}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await parseError(res));
}
