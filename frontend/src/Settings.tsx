import { useEffect, useState } from "react";
import {
  clearChats,
  clearLibrary,
  getSettingsStatus,
  SettingsStatus,
} from "./api";
import ModelsPanel from "./ModelsPanel";
import { applyTheme, getTheme, ThemeMode } from "./theme";

type Tab = "models" | "appearance" | "danger";

const TABS: { id: Tab; label: string }[] = [
  { id: "models", label: "Models" },
  { id: "appearance", label: "Appearance" },
  { id: "danger", label: "Danger zone" },
];

type Props = {
  onBack: () => void;
  onWorkspaceCleared?: () => void;
  pushToast?: (text: string, tone?: "ok" | "error") => void;
};

export default function Settings({ onBack, onWorkspaceCleared, pushToast }: Props) {
  const [tab, setTab] = useState<Tab>("models");
  const [status, setStatus] = useState<SettingsStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [theme, setTheme] = useState<ThemeMode>(getTheme());
  const [busy, setBusy] = useState(false);

  async function refresh() {
    const next = await getSettingsStatus();
    setStatus(next);
  }

  useEffect(() => {
    refresh().catch((err) =>
      setError(err instanceof Error ? err.message : "Failed to load settings")
    );
  }, [tab]);

  function onThemeChange(next: ThemeMode) {
    setTheme(next);
    applyTheme(next);
    pushToast?.(next === "dark" ? "Dark theme on" : "Light theme on");
  }

  async function onClearChats() {
    if (!confirm("Delete all chat history? This cannot be undone.")) return;
    setBusy(true);
    setError(null);
    try {
      const res = await clearChats();
      await refresh();
      onWorkspaceCleared?.();
      pushToast?.(`Cleared ${res.deleted_sessions} chat(s)`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to clear chats");
    } finally {
      setBusy(false);
    }
  }

  async function onClearLibrary() {
    if (!confirm("Delete all PDFs and chunks? This cannot be undone.")) return;
    setBusy(true);
    setError(null);
    try {
      const res = await clearLibrary();
      await refresh();
      onWorkspaceCleared?.();
      pushToast?.(`Removed ${res.deleted_documents} document(s)`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to clear library");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="settings-shell">
      <header className="settings-top">
        <button type="button" className="btn-text" onClick={onBack}>
          ← Back to chat
        </button>
        <div>
          <h1>Settings</h1>
          <p>Manage models, appearance, and workspace risk actions.</p>
        </div>
      </header>

      <div className="settings-layout">
        <nav className="settings-nav" aria-label="Settings sections">
          {TABS.map((item) => (
            <button
              key={item.id}
              type="button"
              className={tab === item.id ? "active" : ""}
              onClick={() => setTab(item.id)}
            >
              {item.label}
            </button>
          ))}
        </nav>

        <section className="settings-panel">
          {error && <p className="error banner">{error}</p>}

          {tab === "models" && <ModelsPanel />}

          {tab === "appearance" && (
            <div className="settings-card">
              <h2>Appearance</h2>
              <p className="muted">Choose a theme for this browser. Preference is saved locally.</p>
              <div className="theme-grid">
                <button
                  type="button"
                  className={`theme-card ${theme === "light" ? "active" : ""}`}
                  onClick={() => onThemeChange("light")}
                >
                  <span className="theme-swatch light" />
                  <strong>Light</strong>
                  <small>Bright workspace</small>
                </button>
                <button
                  type="button"
                  className={`theme-card ${theme === "dark" ? "active" : ""}`}
                  onClick={() => onThemeChange("dark")}
                >
                  <span className="theme-swatch dark" />
                  <strong>Dark</strong>
                  <small>Low-glare night mode</small>
                </button>
              </div>
            </div>
          )}

          {tab === "danger" && (
            <div className="settings-card danger-card">
              <h2>Danger zone</h2>
              <p className="muted">These actions permanently delete workspace data for your account.</p>

              <div className="danger-row">
                <div>
                  <strong>Clear all chats</strong>
                  <small>
                    {status?.workspace
                      ? `${status.workspace.session_count} session(s)`
                      : "Removes chat history"}
                  </small>
                </div>
                <button
                  type="button"
                  className="btn-danger"
                  disabled={busy}
                  onClick={onClearChats}
                >
                  Clear chats
                </button>
              </div>

              <div className="danger-row">
                <div>
                  <strong>Clear PDF library</strong>
                  <small>
                    {status?.workspace
                      ? `${status.workspace.document_count} document(s)`
                      : "Removes uploads and chunks"}
                  </small>
                </div>
                <button
                  type="button"
                  className="btn-danger"
                  disabled={busy}
                  onClick={onClearLibrary}
                >
                  Clear library
                </button>
              </div>
            </div>
          )}

          {status && (
            <div className="settings-meta">
              <h3>Storage</h3>
              <dl>
                <div>
                  <dt>Engine</dt>
                  <dd>{status.storage}</dd>
                </div>
                <div>
                  <dt>Database</dt>
                  <dd>
                    <code>{status.database_path}</code>
                  </dd>
                </div>
                <div>
                  <dt>Uploads</dt>
                  <dd>
                    <code>{status.upload_dir}</code>
                  </dd>
                </div>
                {status.models && (
                  <>
                    <div>
                      <dt>Models</dt>
                      <dd>{status.models.count}</dd>
                    </div>
                    <div>
                      <dt>Default chat</dt>
                      <dd>{status.models.default_chat || "—"}</dd>
                    </div>
                    <div>
                      <dt>Default embed</dt>
                      <dd>{status.models.default_embedding || "—"}</dd>
                    </div>
                  </>
                )}
              </dl>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
