import { useEffect, useState } from "react";
import { getSettingsStatus, SettingsStatus } from "./api";

type Tab = "models" | "appearance" | "danger";

const TABS: { id: Tab; label: string }[] = [
  { id: "models", label: "Models" },
  { id: "appearance", label: "Appearance" },
  { id: "danger", label: "Danger zone" },
];

type Props = {
  onBack: () => void;
};

export default function Settings({ onBack }: Props) {
  const [tab, setTab] = useState<Tab>("models");
  const [status, setStatus] = useState<SettingsStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getSettingsStatus()
      .then(setStatus)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load settings"));
  }, []);

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

          {tab === "models" && (
            <div className="settings-card">
              <h2>Models</h2>
              <p className="muted">
                Add OpenAI and Anthropic models here. API keys stay on the server.
              </p>
              <div className="coming-soon">
                <strong>Coming in PR2</strong>
                <span>
                  {status?.sections.models.note ||
                    "Configure chat + embedding models without editing code."}
                </span>
              </div>
            </div>
          )}

          {tab === "appearance" && (
            <div className="settings-card">
              <h2>Appearance</h2>
              <p className="muted">Theme and display preferences for the workspace.</p>
              <div className="coming-soon">
                <strong>Coming in PR6</strong>
                <span>
                  {status?.sections.appearance.note || "Light / dark theme toggle."}
                </span>
              </div>
            </div>
          )}

          {tab === "danger" && (
            <div className="settings-card">
              <h2>Danger zone</h2>
              <p className="muted">Reset chats or clear your PDF library.</p>
              <div className="coming-soon danger">
                <strong>Coming in PR6</strong>
                <span>
                  {status?.sections.danger.note || "Destructive reset actions."}
                </span>
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
              </dl>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
