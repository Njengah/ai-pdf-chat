import { FormEvent, useEffect, useState } from "react";
import {
  LLMModel,
  LLMModelInput,
  createModel,
  deleteModel,
  listModels,
  setDefaultModel,
  updateModel,
} from "./api";

const emptyForm: LLMModelInput = {
  name: "",
  provider: "openai",
  model_id: "",
  kind: "chat",
  base_url: "",
  api_key: "",
  is_default: true,
};

export default function ModelsPanel() {
  const [models, setModels] = useState<LLMModel[]>([]);
  const [form, setForm] = useState<LLMModelInput>(emptyForm);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);

  async function refresh() {
    const items = await listModels();
    setModels(items);
  }

  useEffect(() => {
    refresh().catch((err) => setError(err.message));
  }, []);

  function resetForm() {
    setForm(emptyForm);
    setEditingId(null);
  }

  function startEdit(model: LLMModel) {
    setEditingId(model.id);
    setForm({
      name: model.name,
      provider: model.provider === "anthropic" ? "anthropic" : "openai",
      model_id: model.model_id,
      kind: model.kind === "embedding" ? "embedding" : "chat",
      base_url: model.base_url || "",
      api_key: "",
      is_default: model.is_default,
    });
    setOk(null);
    setError(null);
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setOk(null);
    try {
      const payload: LLMModelInput = {
        ...form,
        name: form.name.trim(),
        model_id: form.model_id.trim(),
        base_url: form.base_url?.trim() || "",
        api_key: form.api_key?.trim() || "",
      };
      if (editingId) {
        const patch: Partial<LLMModelInput> = {
          name: payload.name,
          provider: payload.provider,
          model_id: payload.model_id,
          kind: payload.kind,
          base_url: payload.base_url,
          is_default: payload.is_default,
        };
        if (payload.api_key) patch.api_key = payload.api_key;
        await updateModel(editingId, patch);
        setOk("Model updated");
      } else {
        await createModel(payload);
        setOk("Model added");
      }
      resetForm();
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setBusy(false);
    }
  }

  async function onDefault(id: string) {
    setBusy(true);
    setError(null);
    try {
      await setDefaultModel(id);
      await refresh();
      setOk("Default updated");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to set default");
    } finally {
      setBusy(false);
    }
  }

  async function onDelete(id: string) {
    if (!confirm("Delete this model config?")) return;
    setBusy(true);
    setError(null);
    try {
      await deleteModel(id);
      if (editingId === id) resetForm();
      await refresh();
      setOk("Model deleted");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="models-panel">
      <div className="settings-card">
        <h2>Models</h2>
        <p className="muted">
          Add OpenAI chat/embedding models and Anthropic chat models. API keys are encrypted
          server-side and never shown in full.
        </p>

        <form className="model-form" onSubmit={onSubmit}>
          <div className="form-grid">
            <label>
              Display name
              <input
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="GPT-4o mini"
                required
              />
            </label>
            <label>
              Provider
              <select
                value={form.provider}
                onChange={(e) => {
                  const provider = e.target.value as "openai" | "anthropic";
                  setForm({
                    ...form,
                    provider,
                    kind: provider === "anthropic" ? "chat" : form.kind,
                  });
                }}
              >
                <option value="openai">OpenAI</option>
                <option value="anthropic">Anthropic</option>
              </select>
            </label>
            <label>
              Kind
              <select
                value={form.kind}
                onChange={(e) => setForm({ ...form, kind: e.target.value as "chat" | "embedding" })}
                disabled={form.provider === "anthropic"}
              >
                <option value="chat">Chat</option>
                <option value="embedding">Embedding</option>
              </select>
            </label>
            <label>
              Model ID
              <input
                value={form.model_id}
                onChange={(e) => setForm({ ...form, model_id: e.target.value })}
                placeholder={form.provider === "anthropic" ? "claude-sonnet-4-20250514" : "gpt-4o-mini"}
                required
              />
            </label>
            <label className="span-2">
              Base URL (optional)
              <input
                value={form.base_url}
                onChange={(e) => setForm({ ...form, base_url: e.target.value })}
                placeholder={
                  form.provider === "anthropic"
                    ? "https://api.anthropic.com"
                    : "https://api.openai.com/v1"
                }
              />
            </label>
            <label className="span-2">
              API key {editingId ? "(leave blank to keep current)" : ""}
              <input
                type="password"
                value={form.api_key}
                onChange={(e) => setForm({ ...form, api_key: e.target.value })}
                placeholder="sk-..."
                autoComplete="off"
                required={!editingId}
              />
            </label>
          </div>

          <label className="check-row">
            <input
              type="checkbox"
              checked={form.is_default}
              onChange={(e) => setForm({ ...form, is_default: e.target.checked })}
            />
            Set as default for this kind
          </label>

          {error && <p className="error">{error}</p>}
          {ok && <p className="ok">{ok}</p>}

          <div className="form-actions">
            <button type="submit" className="btn-primary" disabled={busy}>
              {busy ? "Saving…" : editingId ? "Update model" : "Add model"}
            </button>
            {editingId && (
              <button type="button" className="btn-text" onClick={resetForm}>
                Cancel edit
              </button>
            )}
          </div>
        </form>
      </div>

      <div className="settings-card">
        <h2>Configured models</h2>
        {models.length === 0 ? (
          <p className="muted">No models yet. Add a chat model to leave local demo mode.</p>
        ) : (
          <ul className="model-list">
            {models.map((model) => (
              <li key={model.id}>
                <div>
                  <strong>{model.name}</strong>
                  <small>
                    {model.provider} · {model.kind} · {model.model_id}
                    {model.is_default ? " · default" : ""}
                  </small>
                  <small className="key-mask">
                    {model.has_api_key ? `Key ${model.api_key_masked}` : "No API key"}
                  </small>
                </div>
                <div className="model-actions">
                  {!model.is_default && (
                    <button type="button" className="btn-text sm" onClick={() => onDefault(model.id)}>
                      Make default
                    </button>
                  )}
                  <button type="button" className="btn-text sm" onClick={() => startEdit(model)}>
                    Edit
                  </button>
                  <button type="button" className="btn-text sm danger" onClick={() => onDelete(model.id)}>
                    Delete
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
