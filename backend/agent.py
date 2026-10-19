"""
All "who answers the chat" logic lives here.

Priority:
  1. OpenRouter   - if an OpenRouter API key is set (Settings screen in the UI, or OPENROUTER_API_KEY in .env)
  2. Your agent   - if AGENT_URL is set in backend/.env
  3. Echo bot     - fallback so the UI works out of the box

stream_reply(messages, chat_id, cfg) yields the reply as text chunks.
`messages` is the full chat history: [{"role": "user"|"assistant", "content": "..."}, ...]
Raise AgentError("message") to show an error in the chat without saving it as a reply.

Custom agent contract (AGENT_URL):
  Request body : {"messages": [...], "chat_id": 12}
  Response     : streamed plain text, Server-Sent Events, or JSON like {"reply": "..."}
"""
import json
import os
import time

import requests


class AgentError(Exception):
    """Shown to the user in the chat, but NOT saved as an assistant message."""


# ---------- which provider is active ----------

def is_configured():
    """True if a custom agent endpoint is set."""
    return bool(os.environ.get('AGENT_URL', '').strip())


def provider(cfg):
    if cfg.get('openrouter_key'):
        return 'openrouter'
    if is_configured():
        return 'http'
    return 'echo'


def stream_reply(messages, chat_id, cfg):
    which = provider(cfg)
    try:
        if which == 'openrouter':
            yield from _call_openrouter(messages, cfg)
        elif which == 'http':
            yield from _call_http_agent(messages, chat_id)
        else:
            yield from _echo(messages)
    except AgentError:
        raise
    except requests.RequestException as e:
        raise AgentError(f'Request failed: {e}') from e
    except Exception as e:  # keep the chat alive if something unexpected happens
        raise AgentError(f'Unexpected error: {e}') from e


# ---------- OpenRouter ----------

def _openrouter_base():
    return os.environ.get('OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1').rstrip('/')


def _call_openrouter(messages, cfg):
    headers = {
        'Authorization': f"Bearer {cfg['openrouter_key']}",
        'Content-Type': 'application/json',
        'HTTP-Referer': 'http://localhost',  # optional attribution headers OpenRouter supports
        'X-Title': 'Agent Chat',
    }
    payload = {'model': cfg['model'], 'messages': messages, 'stream': True}

    with requests.post(
        f'{_openrouter_base()}/chat/completions',
        json=payload,
        headers=headers,
        stream=True,
        timeout=(10, 600),
    ) as r:
        if r.status_code != 200:
            raise AgentError(_openrouter_error(r))

        r.encoding = 'utf-8'
        for line in r.iter_lines(chunk_size=None, decode_unicode=True):
            # skip blanks and SSE comments like ": OPENROUTER PROCESSING"
            if not line or not line.startswith('data:'):
                continue
            data = line[5:].strip()
            if data == '[DONE]':
                break
            try:
                obj = json.loads(data)
            except ValueError:
                continue
            if isinstance(obj, dict) and obj.get('error'):
                err = obj['error']
                msg = err.get('message') if isinstance(err, dict) else str(err)
                raise AgentError(f'OpenRouter error: {msg}')
            choices = obj.get('choices') or []
            if choices:
                text = (choices[0].get('delta') or {}).get('content')
                if text:
                    yield text


def _openrouter_error(r):
    try:
        err = r.json().get('error', {})
        msg = err.get('message') if isinstance(err, dict) else str(err)
    except ValueError:
        msg = r.text[:200]
    hint = {
        401: ' Check your API key in Settings.',
        402: ' Not enough credits on your OpenRouter account.',
        404: ' Check the model name in Settings.',
        429: ' Rate limited, try again in a moment.',
    }.get(r.status_code, '')
    return f'OpenRouter error {r.status_code}: {msg or "request failed"}.{hint}'


_models_cache = {'ok': 0.0, 'tried': 0.0, 'data': []}


def fetch_models():
    """Public model list from OpenRouter (no key needed), cached for an hour."""
    now = time.time()
    stale = not _models_cache['data'] or now - _models_cache['ok'] > 3600
    if stale and now - _models_cache['tried'] > 60:
        _models_cache['tried'] = now
        try:
            r = requests.get(f'{_openrouter_base()}/models', timeout=10)
            r.raise_for_status()
            items = [
                {'id': m['id'], 'name': m.get('name') or m['id']}
                for m in r.json().get('data', [])
                if isinstance(m, dict) and m.get('id')
            ]
            _models_cache['data'] = sorted(items, key=lambda m: m['id'])
            _models_cache['ok'] = now
        except Exception:
            pass
    return _models_cache['data']


# ---------- custom agent over HTTP ----------

def _call_http_agent(messages, chat_id):
    url = os.environ['AGENT_URL'].strip()
    headers = {'Content-Type': 'application/json'}
    key = os.environ.get('AGENT_API_KEY', '').strip()
    if key:
        headers['Authorization'] = f'Bearer {key}'
    payload = {'messages': messages, 'chat_id': chat_id}

    with requests.post(url, json=payload, headers=headers, stream=True, timeout=(10, 600)) as r:
        r.raise_for_status()
        ctype = r.headers.get('Content-Type', '').lower()

        if 'application/json' in ctype:
            yield _text_from(r.json())

        elif 'text/event-stream' in ctype:
            r.encoding = 'utf-8'
            for line in r.iter_lines(chunk_size=None, decode_unicode=True):
                if not line or not line.startswith('data:'):
                    continue
                data = line[5:]
                if data.startswith(' '):
                    data = data[1:]
                if data.strip() == '[DONE]':
                    break
                try:
                    yield _text_from(json.loads(data))
                except ValueError:
                    yield data

        else:  # plain streamed text
            r.encoding = 'utf-8'
            for chunk in r.iter_content(chunk_size=None, decode_unicode=True):
                if chunk:
                    yield chunk


def _text_from(obj):
    """Pull the reply text out of whatever JSON shape the agent returns."""
    if isinstance(obj, str):
        return obj
    if isinstance(obj, dict):
        choices = obj.get('choices')  # OpenAI-style
        if isinstance(choices, list) and choices and isinstance(choices[0], dict):
            c = choices[0]
            return _text_from(c.get('delta') or c.get('message') or c.get('text') or '')
        for key in ('reply', 'response', 'output', 'answer', 'text', 'content', 'message', 'delta'):
            if key in obj:
                val = obj[key]
                if val is None:
                    return ''
                if isinstance(val, (str, dict)):
                    return _text_from(val)
        return json.dumps(obj, ensure_ascii=False)
    if obj is None:
        return ''
    return str(obj)


# ---------- echo fallback ----------

def _echo(messages):
    last = messages[-1]['content'] if messages else ''
    quoted = last.replace('\n', '\n> ')
    text = (
        '**Echo mode** — no AI is connected yet.\n\n'
        'Open **Settings** (bottom left) and paste your OpenRouter API key to get real replies.\n\n'
        f'You said:\n\n> {quoted}'
    )
    for word in text.split(' '):
        yield word + ' '
        time.sleep(0.02)
