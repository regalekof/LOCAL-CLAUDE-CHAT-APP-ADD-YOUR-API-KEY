import { useCallback, useEffect, useRef, useState } from 'react';
import Sidebar from './components/Sidebar.jsx';
import ChatView from './components/ChatView.jsx';
import SettingsModal from './components/SettingsModal.jsx';
import * as api from './api.js';

const LAST_KEY = 'agentchat:lastChatId';

function rememberChat(id) {
  try {
    if (id == null) localStorage.removeItem(LAST_KEY);
    else localStorage.setItem(LAST_KEY, String(id));
  } catch {
    /* storage blocked */
  }
}

const NO_SETTINGS = { provider: '', model: '', openrouter_key_set: false, openrouter_key_hint: '' };

export default function App() {
  const [chats, setChats] = useState([]);
  const [activeId, setActiveId] = useState(null); // null = brand-new chat (created on first send)
  const [messages, setMessages] = useState([]);
  const [streaming, setStreaming] = useState(false);
  const [settings, setSettings] = useState(NO_SETTINGS);
  const [showSettings, setShowSettings] = useState(false);
  const [error, setError] = useState('');
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const abortRef = useRef(null);

  const refreshChats = useCallback(
    () => api.listChats().then(setChats).catch((e) => setError(`Backend not reachable: ${e.message}`)),
    []
  );

  useEffect(() => {
    (async () => {
      try {
        const list = await api.listChats();
        setChats(list);
        // reopen the chat you were in before the refresh
        const saved = Number(localStorage.getItem(LAST_KEY));
        if (saved && list.some((c) => c.id === saved)) openChat(saved);
      } catch (e) {
        setError(`Backend not reachable: ${e.message}`);
      }
    })();
    api.getSettings().then(setSettings).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const stop = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
  }, []);

  const openChat = async (id) => {
    stop();
    setStreaming(false);
    setError('');
    setActiveId(id);
    rememberChat(id);
    if (id == null) {
      setMessages([]);
      return;
    }
    try {
      const chat = await api.getChat(id);
      setMessages(chat.messages);
    } catch (e) {
      setError(e.message);
    }
  };

  const send = async (text) => {
    const content = text.trim();
    if (!content || streaming) return;

    setError('');
    const controller = new AbortController();
    abortRef.current = controller;
    setStreaming(true);

    try {
      let id = activeId;
      if (id == null) {
        const chat = await api.createChat();
        id = chat.id;
        setActiveId(id);
        rememberChat(id);
      }
      setMessages((m) => [...m, { role: 'user', content }, { role: 'assistant', content: '' }]);

      await api.streamMessage(
        id,
        content,
        (chunk) => {
          if (abortRef.current !== controller) return; // user stopped or switched chats
          setMessages((m) => {
            const copy = m.slice();
            const last = copy[copy.length - 1];
            copy[copy.length - 1] = { ...last, content: last.content + chunk };
            return copy;
          });
        },
        controller.signal
      );
    } catch (e) {
      if (e.name !== 'AbortError') {
        setError(e.message || 'Something went wrong');
        // drop the empty assistant bubble if nothing arrived
        setMessages((m) => {
          const last = m[m.length - 1];
          return last && last.role === 'assistant' && !last.content ? m.slice(0, -1) : m;
        });
      }
    } finally {
      if (abortRef.current === controller || abortRef.current === null) {
        abortRef.current = null;
        setStreaming(false);
      }
      refreshChats();
    }
  };

  const removeChat = async (id) => {
    try {
      await api.deleteChat(id);
      if (id === activeId) {
        stop();
        setStreaming(false);
        setActiveId(null);
        setMessages([]);
        rememberChat(null);
      }
      refreshChats();
    } catch (e) {
      setError(e.message);
    }
  };

  const renameChat = async (id, title) => {
    try {
      await api.renameChat(id, title);
      refreshChats();
    } catch (e) {
      setError(e.message);
    }
  };

  const activeChat = chats.find((c) => c.id === activeId);
  const openSettings = () => setShowSettings(true);

  return (
    <div className={`app ${sidebarOpen ? '' : 'collapsed'}`}>
      <Sidebar
        chats={chats}
        activeId={activeId}
        onNew={() => openChat(null)}
        onSelect={openChat}
        onDelete={removeChat}
        onRename={renameChat}
        onOpenSettings={openSettings}
      />
      <ChatView
        title={activeChat ? activeChat.title : 'New chat'}
        chatKey={activeId}
        messages={messages}
        streaming={streaming}
        error={error}
        provider={settings.provider}
        model={settings.model}
        onSend={send}
        onStop={stop}
        onToggleSidebar={() => setSidebarOpen((o) => !o)}
        onOpenSettings={openSettings}
      />
      {showSettings && (
        <SettingsModal
          settings={settings}
          onClose={() => setShowSettings(false)}
          onSaved={setSettings}
        />
      )}
    </div>
  );
}
