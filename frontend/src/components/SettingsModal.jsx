import { useEffect, useState } from 'react';
import * as api from '../api.js';

export default function SettingsModal({ settings, onClose, onSaved }) {
  const [key, setKey] = useState('');
  const [model, setModel] = useState(settings.model || '');
  const [models, setModels] = useState([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    api.getModels().then(setModels).catch(() => {});
  }, []);

  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const save = async (patch) => {
    setSaving(true);
    setError('');
    try {
      const next = await api.saveSettings(patch);
      onSaved(next);
      onClose();
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  const submit = (e) => {
    e.preventDefault();
    const patch = { model: model.trim() };
    if (key.trim()) patch.openrouter_api_key = key.trim(); // blank = keep the saved key
    save(patch);
  };

  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <form className="modal" onSubmit={submit}>
        <h2>Settings</h2>

        <label>
          OpenRouter API key
          <input
            type="password"
            autoComplete="off"
            spellCheck={false}
            autoFocus
            value={key}
            onChange={(e) => setKey(e.target.value)}
            placeholder={
              settings.openrouter_key_set
                ? `Saved (${settings.openrouter_key_hint}), leave blank to keep`
                : 'sk-or-v1-…'
            }
          />
        </label>
        <p className="help">
          Create one at{' '}
          <a href="https://openrouter.ai/keys" target="_blank" rel="noreferrer">
            openrouter.ai/keys
          </a>
          . It's stored only on this computer (in <code>backend/chats.db</code>) and sent only to OpenRouter.
        </p>

        <label>
          Model
          <input
            list="model-list"
            value={model}
            onChange={(e) => setModel(e.target.value)}
            placeholder="openrouter/auto"
            spellCheck={false}
          />
          <datalist id="model-list">
            {models.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name}
              </option>
            ))}
          </datalist>
        </label>
        <p className="help">
          Clear the field and type to search (e.g. <code>claude</code>, <code>gpt</code>, <code>gemini</code>,{' '}
          <code>llama</code>). <code>openrouter/auto</code> picks a model for you.
        </p>

        {settings.openrouter_key_set && (
          <button type="button" className="link-danger" onClick={() => save({ openrouter_api_key: '' })}>
            Remove saved key
          </button>
        )}

        {error && <div className="error">{error}</div>}

        <div className="modal-actions">
          <button type="button" className="btn" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="btn primary" disabled={saving}>
            Save
          </button>
        </div>
      </form>
    </div>
  );
}
