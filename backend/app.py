import os
import re
import sqlite3
import sys
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # reads backend/.env

from flask import Flask, Response, jsonify, request, send_from_directory  # noqa: E402

import agent  # noqa: E402

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = os.environ.get('DB_PATH', str(BASE_DIR / 'chats.db'))
if getattr(sys, 'frozen', False):  # running as the packaged desktop app
    DIST_DIR = Path(sys._MEIPASS) / 'dist'
else:
    DIST_DIR = BASE_DIR.parent / 'frontend' / 'dist'

SCHEMA = """
CREATE TABLE IF NOT EXISTS chats (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    title      TEXT NOT NULL DEFAULT 'New chat',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id    INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    role       TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content    TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_chat ON messages (chat_id, id);
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

DEFAULT_MODEL = 'openrouter/auto'

app = Flask(__name__, static_folder=None)


# ---------- database helpers ----------

def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def db_all(sql, args=()):
    with closing(connect()) as conn:
        return [dict(r) for r in conn.execute(sql, args).fetchall()]


def db_one(sql, args=()):
    with closing(connect()) as conn:
        row = conn.execute(sql, args).fetchone()
        return dict(row) if row else None


def db_exec(sql, args=()):
    with closing(connect()) as conn, conn:  # inner `conn` = commit on success
        return conn.execute(sql, args).lastrowid


def init_db():
    with closing(connect()) as conn:
        conn.executescript(SCHEMA)
    try:
        os.chmod(DB_PATH, 0o600)  # the DB can hold your API key: owner-only (no effect on Windows)
    except OSError:
        pass


def get_setting(key, default=''):
    row = db_one('SELECT value FROM settings WHERE key = ?', (key,))
    return row['value'] if row else default


def set_setting(key, value):
    db_exec(
        'INSERT INTO settings (key, value) VALUES (?, ?) '
        'ON CONFLICT(key) DO UPDATE SET value = excluded.value',
        (key, value),
    )


def runtime_config():
    """Settings saved in the UI win over .env values."""
    return {
        'openrouter_key': get_setting('openrouter_api_key') or os.environ.get('OPENROUTER_API_KEY', '').strip(),
        'model': get_setting('model') or os.environ.get('OPENROUTER_MODEL', '').strip() or DEFAULT_MODEL,
    }


def settings_payload():
    cfg = runtime_config()
    key = cfg['openrouter_key']
    return {
        'provider': agent.provider(cfg),  # 'openrouter' | 'http' | 'echo'
        'model': cfg['model'],
        'openrouter_key_set': bool(key),
        'openrouter_key_hint': ('…' + key[-4:]) if len(key) >= 8 else '',  # never the full key
    }


def make_title(text):
    title = re.sub(r'\s+', ' ', text).strip()
    return title if len(title) <= 50 else title[:47].rstrip() + '...'


init_db()


# ---------- API ----------

@app.get('/api/health')
def health():
    return jsonify(status='ok', agent_mode=agent.provider(runtime_config()))


@app.get('/api/settings')
def get_settings():
    return jsonify(settings_payload())


@app.put('/api/settings')
def put_settings():
    data = request.get_json(silent=True) or {}
    if 'openrouter_api_key' in data:
        key = str(data['openrouter_api_key'] or '').strip()
        if len(key) > 300 or any(c.isspace() for c in key):
            return jsonify(error='That does not look like an API key'), 400
        set_setting('openrouter_api_key', key)  # empty string = remove the saved key
    if 'model' in data:
        model = str(data['model'] or '').strip()
        if len(model) > 200 or any(c.isspace() for c in model):
            return jsonify(error='That does not look like a model id'), 400
        set_setting('model', model)
    return jsonify(settings_payload())


@app.get('/api/models')
def list_models():
    return jsonify(agent.fetch_models())


@app.get('/api/chats')
def list_chats():
    return jsonify(db_all(
        'SELECT id, title, created_at, updated_at FROM chats ORDER BY updated_at DESC, id DESC'
    ))


@app.post('/api/chats')
def create_chat():
    data = request.get_json(silent=True) or {}
    title = (data.get('title') or 'New chat').strip()[:120] or 'New chat'
    ts = now()
    chat_id = db_exec(
        'INSERT INTO chats (title, created_at, updated_at) VALUES (?, ?, ?)', (title, ts, ts)
    )
    chat = db_one('SELECT id, title, created_at, updated_at FROM chats WHERE id = ?', (chat_id,))
    return jsonify(chat), 201


@app.get('/api/chats/<int:chat_id>')
def get_chat(chat_id):
    chat = db_one('SELECT id, title, created_at, updated_at FROM chats WHERE id = ?', (chat_id,))
    if not chat:
        return jsonify(error='Chat not found'), 404
    chat['messages'] = db_all(
        'SELECT id, role, content, created_at FROM messages WHERE chat_id = ? ORDER BY id', (chat_id,)
    )
    return jsonify(chat)


@app.patch('/api/chats/<int:chat_id>')
def rename_chat(chat_id):
    if not db_one('SELECT id FROM chats WHERE id = ?', (chat_id,)):
        return jsonify(error='Chat not found'), 404
    title = ((request.get_json(silent=True) or {}).get('title') or '').strip()[:120]
    if not title:
        return jsonify(error='Title required'), 400
    db_exec('UPDATE chats SET title = ? WHERE id = ?', (title, chat_id))
    return jsonify(db_one('SELECT id, title, created_at, updated_at FROM chats WHERE id = ?', (chat_id,)))


@app.delete('/api/chats/<int:chat_id>')
def delete_chat(chat_id):
    if not db_one('SELECT id FROM chats WHERE id = ?', (chat_id,)):
        return jsonify(error='Chat not found'), 404
    db_exec('DELETE FROM chats WHERE id = ?', (chat_id,))  # messages go with it (ON DELETE CASCADE)
    return jsonify(ok=True)


@app.post('/api/chats/<int:chat_id>/messages')
def send_message(chat_id):
    chat = db_one('SELECT id, title FROM chats WHERE id = ?', (chat_id,))
    if not chat:
        return jsonify(error='Chat not found'), 404
    content = ((request.get_json(silent=True) or {}).get('content') or '').strip()
    if not content:
        return jsonify(error='Empty message'), 400

    ts = now()
    db_exec(
        'INSERT INTO messages (chat_id, role, content, created_at) VALUES (?, ?, ?, ?)',
        (chat_id, 'user', content, ts),
    )
    if chat['title'] == 'New chat':
        db_exec('UPDATE chats SET title = ? WHERE id = ?', (make_title(content), chat_id))
    db_exec('UPDATE chats SET updated_at = ? WHERE id = ?', (ts, chat_id))

    history = db_all('SELECT role, content FROM messages WHERE chat_id = ? ORDER BY id', (chat_id,))
    cfg = runtime_config()

    def generate():
        parts = []
        try:
            for piece in agent.stream_reply(history, chat_id, cfg):
                if piece:
                    parts.append(piece)
                    yield piece
        except agent.AgentError as e:
            # shown live in the chat, but not saved as an assistant message
            yield ('\n\n' if parts else '') + f'⚠️ {e}'
        finally:
            # Runs on normal finish AND when the client hits Stop, so partial replies are saved too
            reply = ''.join(parts).strip()
            if reply:
                ts2 = now()
                db_exec(
                    'INSERT INTO messages (chat_id, role, content, created_at) VALUES (?, ?, ?, ?)',
                    (chat_id, 'assistant', reply, ts2),
                )
                db_exec('UPDATE chats SET updated_at = ? WHERE id = ?', (ts2, chat_id))

    return Response(
        generate(),
        mimetype='text/plain',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
    )


# ---------- serve the built frontend (after `npm run build`) ----------

@app.get('/', defaults={'path': ''})
@app.get('/<path:path>')
def spa(path):
    if path.startswith('api/'):
        return jsonify(error='Not found'), 404
    if DIST_DIR.exists():
        if path and (DIST_DIR / path).is_file():
            return send_from_directory(DIST_DIR, path)
        return send_from_directory(DIST_DIR, 'index.html')
    return 'Frontend not built yet. Use the dev server (npm run dev) or run npm run build.', 200


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='127.0.0.1', port=port, debug=os.environ.get('FLASK_DEBUG', '1') == '1')
