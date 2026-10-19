import { useMemo, useRef, useState } from 'react';

const DAY = 24 * 60 * 60 * 1000;

function groupLabel(iso) {
  const startOfToday = new Date();
  startOfToday.setHours(0, 0, 0, 0);
  const t = new Date(iso).getTime();
  const s = startOfToday.getTime();
  if (t >= s) return 'Today';
  if (t >= s - DAY) return 'Yesterday';
  if (t >= s - 7 * DAY) return 'Previous 7 days';
  return 'Older';
}

export default function Sidebar({ chats, activeId, onNew, onSelect, onDelete, onRename, onOpenSettings }) {
  const [query, setQuery] = useState('');
  const [editingId, setEditingId] = useState(null);
  const [draft, setDraft] = useState('');
  const cancelled = useRef(false);

  const groups = useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = q ? chats.filter((c) => c.title.toLowerCase().includes(q)) : chats;
    const out = [];
    for (const c of list) {
      const label = groupLabel(c.updated_at);
      const last = out[out.length - 1];
      if (last && last.label === label) last.items.push(c);
      else out.push({ label, items: [c] });
    }
    return out;
  }, [chats, query]);

  const startRename = (c) => {
    cancelled.current = false;
    setEditingId(c.id);
    setDraft(c.title);
  };

  const finishRename = (c) => {
    const title = draft.trim();
    if (!cancelled.current && title && title !== c.title) onRename(c.id, title);
    setEditingId(null);
  };

  return (
    <aside className="sidebar">
      <div className="sidebar-head">
        <span className="brand">Agent Chat</span>
      </div>

      <button className="new-chat" onClick={onNew}>
        <span className="plus">+</span> New chat
      </button>

      <input
        className="search"
        placeholder="Search chats"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />

      <nav className="chat-list">
        {groups.length === 0 && <p className="empty-list">{query ? 'No matches' : 'No chats yet'}</p>}

        {groups.map((g) => (
          <div key={g.label}>
            <div className="group-label">{g.label}</div>
            {g.items.map((c) => (
              <div
                key={c.id}
                role="button"
                tabIndex={0}
                className={`chat-item ${c.id === activeId ? 'active' : ''}`}
                onClick={() => onSelect(c.id)}
                onKeyDown={(e) => e.key === 'Enter' && e.target === e.currentTarget && onSelect(c.id)}
              >
                {editingId === c.id ? (
                  <input
                    className="rename"
                    autoFocus
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                    onFocus={(e) => e.target.select()}
                    onClick={(e) => e.stopPropagation()}
                    onBlur={() => finishRename(c)}
                    onKeyDown={(e) => {
                      if (e.nativeEvent.isComposing) return;
                      if (e.key === 'Enter') e.currentTarget.blur();
                      if (e.key === 'Escape') {
                        cancelled.current = true;
                        e.currentTarget.blur();
                      }
                    }}
                  />
                ) : (
                  <>
                    <span className="chat-title" title={c.title} onDoubleClick={() => startRename(c)}>
                      {c.title}
                    </span>
                    <span className="chat-actions">
                      <button
                        title="Rename"
                        onClick={(e) => {
                          e.stopPropagation();
                          startRename(c);
                        }}
                      >
                        ✎
                      </button>
                      <button
                        title="Delete"
                        onClick={(e) => {
                          e.stopPropagation();
                          if (window.confirm('Delete this chat?')) onDelete(c.id);
                        }}
                      >
                        ✕
                      </button>
                    </span>
                  </>
                )}
              </div>
            ))}
          </div>
        ))}
      </nav>

      <button className="settings-btn" onClick={onOpenSettings}>
        ⚙ Settings
      </button>
    </aside>
  );
}
