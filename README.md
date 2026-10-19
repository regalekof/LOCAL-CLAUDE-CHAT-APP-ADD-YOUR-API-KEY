# Agent Chat

Local Claude-style chat UI for your own agent. Multiple chats, saved in a local SQLite file (`backend/chats.db`).

## Run it (2 terminals)

**Backend**
```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate     Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # Windows: copy .env.example .env
python app.py               # http://127.0.0.1:5001
```

**Frontend**
```bash
cd frontend
npm install
npm run dev                 # http://localhost:5173  <- open this
```

Optional single-server mode: `npm run build` in `frontend/`, then just run the backend and open http://127.0.0.1:5001.

## Build it as Windows software (installer + double-click app)

Result: `AgentChat-Setup-1.0.0.exe` (installer with Start-menu entry, optional desktop shortcut, uninstaller) and a portable `AgentChat.exe`. The app opens in its own window, no terminals, no browser tab.

**Option A: on your PC.** Install Python 3.10+ and Node 18+ (and optionally [Inno Setup 6](https://jrsoftware.org/isdl.php) for the installer), then double-click **`build_windows.bat`**. Output lands in `release/`. The script also runs a smoke test on the finished exe.

**Option B: in the cloud, nothing to install.** Push this folder to a GitHub repo → **Actions** tab → **Build Windows app** → **Run workflow**. Download the `AgentChat-Windows` artifact when it finishes. Push a tag like `v1.0.0` to also publish a GitHub Release.

Good to know:
- **Your data** (chats, API key) lives in `%APPDATA%\AgentChat\`, not inside the program, so updates and reinstalls keep it. To bring over existing dev chats, copy `backend\chats.db` there before first launch. Logs are in `agentchat.log` in the same folder.
- **Windows SmartScreen** will say "Windows protected your PC" for an unsigned app: click *More info → Run anyway*. Removing the warning needs a paid code-signing certificate (sign `AgentChat.exe` and the installer).
- The window uses Microsoft Edge WebView2 (already on Windows 11 and up-to-date Windows 10). If it's missing, the app falls back to opening your browser.
- Bump `VERSION` for each release.
- To run the desktop window from source: `cd frontend && npm run build`, then `cd backend && pip install pywebview && python desktop.py`.

## Use OpenRouter (any model)

Open the app → **Settings** (bottom left) → paste your OpenRouter API key → pick a model (search by typing, e.g. `claude`, `gpt`, `gemini`) → Save. No restart needed. Click the model badge at the top to change it later.

The key is stored locally in `backend/chats.db` and is never sent back to the browser; the backend only sends it to OpenRouter. You can also put `OPENROUTER_API_KEY` / `OPENROUTER_MODEL` in `backend/.env` instead. Don't share or commit `chats.db`.

Priority: OpenRouter key → your own agent (`AGENT_URL`) → echo mode. To go back to your own agent, use "Remove saved key" in Settings.

## Connect your own agent

Put your endpoint in `backend/.env`:

```
AGENT_URL=http://localhost:8000/chat
AGENT_API_KEY=            # optional
```

The backend POSTs the whole chat history:

```json
{ "messages": [{ "role": "user", "content": "hi" }, { "role": "assistant", "content": "hello" }], "chat_id": 3 }
```

Your agent can answer with streamed plain text, Server-Sent Events, or JSON like `{"reply": "..."}`.

FastAPI example (streaming):

```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

app = FastAPI()

@app.post("/chat")
async def chat(body: dict):
    async def gen():
        # replace with your LangGraph / LangChain streaming
        for word in "Hello from my agent".split():
            yield word + " "
    return StreamingResponse(gen(), media_type="text/plain")
```

Want to call a Python agent in-process instead of over HTTP? Edit `stream_reply()` in `backend/agent.py`.

Without `AGENT_URL` the app runs in **echo mode** so you can test the UI.

## API

| Method | Path | |
|---|---|---|
| GET / POST | `/api/chats` | list / create |
| GET / PATCH / DELETE | `/api/chats/<id>` | open (with messages) / rename / delete |
| POST | `/api/chats/<id>/messages` | send a message, streams the reply |
