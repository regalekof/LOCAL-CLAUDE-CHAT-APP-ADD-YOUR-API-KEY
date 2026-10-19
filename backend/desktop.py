"""
Desktop launcher: runs the local server and shows Agent Chat in its own window.

  python desktop.py              dev run (needs: frontend built with `npm run build`)
  AgentChat.exe                  the packaged app (built by build_windows.bat / GitHub Actions)
  AgentChat.exe --selftest       smoke test, exits 0 if everything works (used by CI)
  AGENTCHAT_NO_WINDOW=1          serve only, no window (prints the URL)

Your chats and API key live in a per-user data folder, NOT next to the program:
  Windows  %APPDATA%\\AgentChat       Mac  ~/Library/Application Support/AgentChat
  Linux    ~/.local/share/AgentChat
"""
import json
import os
import re
import socket
import sys
import tempfile
import threading
import time
import traceback
import urllib.request
import webbrowser
from pathlib import Path

APP_NAME = 'AgentChat'
WINDOW_TITLE = 'Agent Chat'
# A fixed port keeps the browser-side storage origin stable between launches
PREFERRED_PORT = 47615


def data_dir():
    if sys.platform == 'win32':
        base = Path(os.environ.get('APPDATA') or Path.home() / 'AppData' / 'Roaming')
    elif sys.platform == 'darwin':
        base = Path.home() / 'Library' / 'Application Support'
    else:
        base = Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local' / 'share')
    path = base / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def setup_logging(data):
    """A windowed .exe has no console (stdout/stderr are None), so log to a file instead."""
    log_path = data / 'agentchat.log'
    try:
        if log_path.exists() and log_path.stat().st_size > 1_000_000:
            log_path.unlink()
        log = open(log_path, 'a', encoding='utf-8', buffering=1)
    except OSError:
        return
    if sys.stdout is None:
        sys.stdout = log
    if sys.stderr is None:
        sys.stderr = log
    import logging

    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    logging.basicConfig(stream=log, level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')


def pick_port():
    for port in (PREFERRED_PORT, 0):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind(('127.0.0.1', port))
            return s.getsockname()[1]
        except OSError:
            continue
        finally:
            s.close()
    raise RuntimeError('No free port available')


def wait_until_up(url, seconds=15):
    end = time.time() + seconds
    while time.time() < end:
        try:
            urllib.request.urlopen(url + 'api/health', timeout=1).read()
            return True
        except Exception:
            time.sleep(0.1)
    return False


# ---------- window ----------

class WindowApi:
    """Exposed to the page as window.pywebview.api (used to open links in the real browser)."""

    def open_external(self, url):
        if isinstance(url, str) and url.lower().startswith(('http://', 'https://')):
            webbrowser.open(url)


def browser_fallback(url):
    """No embedded window available (e.g. WebView2 missing): use the default browser."""
    webbrowser.open(url)
    if sys.platform == 'win32':
        import ctypes

        ctypes.windll.user32.MessageBoxW(
            0,
            'Agent Chat is running in your browser.\n\nClick OK to quit the app.',
            WINDOW_TITLE,
            0x40,
        )
    else:
        print(f'Agent Chat is running at {url}  (Ctrl+C to quit)')
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            pass


def open_window(url, data):
    try:
        import webview
    except Exception:
        traceback.print_exc()
        return browser_fallback(url)

    try:
        webview.create_window(
            WINDOW_TITLE, url, js_api=WindowApi(), width=1280, height=820, min_size=(820, 520)
        )
        opts = {
            'private_mode': False,  # keep localStorage etc. between launches
            'storage_path': str(data / 'webview'),
        }
        if sys.platform == 'win32':
            opts['gui'] = 'edgechromium'  # fail loudly instead of falling back to the old IE engine
        webview.start(**opts)
    except Exception:
        traceback.print_exc()
        browser_fallback(url)


# ---------- smoke test ----------

def selftest(url):
    """Exercises the packaged app end to end. Returns 0 on success."""

    def get(path):
        return urllib.request.urlopen(url + path.lstrip('/'), timeout=15).read()

    def post(path, payload):
        req = urllib.request.Request(
            url + path.lstrip('/'),
            data=json.dumps(payload).encode(),
            headers={'Content-Type': 'application/json'},
        )
        return urllib.request.urlopen(req, timeout=30).read()

    steps = []

    def check(name, fn):
        try:
            ok = fn()
        except Exception as e:
            ok = False
            print(f'selftest {name}: {e!r}')
        steps.append(ok)
        print(f'selftest {name}: {"ok" if ok else "FAILED"}')

    def health():
        return json.loads(get('api/health'))['status'] == 'ok'

    def frontend():
        html = get('/').decode()
        asset = re.search(r'/assets/[^"\']+\.js', html)
        return '<div id="root">' in html and bool(asset) and len(get(asset.group(0))) > 10_000

    def chat_roundtrip():
        chat = json.loads(post('api/chats', {}))
        reply = post(f"api/chats/{chat['id']}/messages", {'content': 'selftest ping'}).decode()
        saved = json.loads(get(f"api/chats/{chat['id']}"))
        return 'selftest ping' in reply and len(saved['messages']) == 2

    def tls_bundle():
        import certifi

        return os.path.exists(certifi.where())

    check('health', health)
    check('frontend', frontend)
    check('chat+streaming+sqlite', chat_roundtrip)
    check('https certificates bundled', tls_bundle)
    return 0 if all(steps) else 1


# ---------- main ----------

def main():
    is_selftest = '--selftest' in sys.argv
    data = data_dir()
    setup_logging(data)

    if is_selftest:
        # isolated DB and no external providers, so the test is deterministic and offline
        os.environ['DB_PATH'] = str(Path(tempfile.mkdtemp()) / 'selftest.db')
        for k in ('OPENROUTER_API_KEY', 'AGENT_URL'):
            os.environ.pop(k, None)
    else:
        os.environ.setdefault('DB_PATH', str(data / 'chats.db'))
    os.environ.setdefault('FLASK_DEBUG', '0')

    # keep .env optional in the packaged app: look in the data folder
    from dotenv import load_dotenv

    load_dotenv(data / '.env')

    from werkzeug.serving import make_server

    import app as backend  # imported after DB_PATH is set (it opens the DB on import)

    port = pick_port()
    server = make_server('127.0.0.1', port, backend.app, threaded=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f'http://127.0.0.1:{port}/'

    if not wait_until_up(url):
        print('Server did not start', file=sys.stderr)
        sys.exit(1)
    print(f'Agent Chat server up at {url} (data: {data})')

    if is_selftest:
        code = selftest(url)
        print('selftest', 'PASSED' if code == 0 else 'FAILED')
        sys.exit(code)

    if os.environ.get('AGENTCHAT_NO_WINDOW') == '1':
        print(url, flush=True)
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            return
    else:
        open_window(url, data)


if __name__ == '__main__':
    main()
