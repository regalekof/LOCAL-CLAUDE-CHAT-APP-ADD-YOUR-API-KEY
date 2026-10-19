import { memo, useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

/* ---------- markdown pieces ---------- */

function Pre({ node, children }) {
  const [copied, setCopied] = useState(false);
  const raw = children?.props?.children;
  const text = Array.isArray(raw) ? raw.join('') : String(raw ?? '');

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text.replace(/\n$/, ''));
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard blocked */
    }
  };

  return (
    <div className="codeblock">
      <button className="copy-code" onClick={copy}>
        {copied ? 'Copied' : 'Copy'}
      </button>
      <pre>{children}</pre>
    </div>
  );
}

const mdComponents = {
  pre: Pre,
  a: ({ node, ...props }) => <a {...props} target="_blank" rel="noreferrer" />,
};

/* ---------- one message ---------- */

const Message = memo(function Message({ role, content, pending }) {
  const [copied, setCopied] = useState(false);

  if (role === 'user') {
    return (
      <div className="msg user">
        <div className="bubble">{content}</div>
      </div>
    );
  }

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard blocked */
    }
  };

  return (
    <div className="msg assistant">
      {content ? (
        <div className="md">
          <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>
            {content}
          </ReactMarkdown>
        </div>
      ) : pending ? (
        <div className="dots">
          <span />
          <span />
          <span />
        </div>
      ) : null}
      {content && !pending && (
        <div className="msg-actions">
          <button onClick={copy}>{copied ? 'Copied' : 'Copy'}</button>
        </div>
      )}
    </div>
  );
});

/* ---------- composer ---------- */

function Composer({ streaming, focusKey, onSend, onStop }) {
  const [text, setText] = useState('');
  const ref = useRef(null);

  useEffect(() => {
    ref.current?.focus();
  }, [focusKey]);

  // auto-grow the textarea up to 200px
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 200) + 'px';
  }, [text]);

  const submit = () => {
    if (!text.trim() || streaming) return;
    onSend(text);
    setText('');
  };

  const onKeyDown = (e) => {
    // Enter sends, Shift+Enter = newline, ignore Enter while an IME (CJK etc.) is composing
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <div className="composer-wrap">
      <div className="composer">
        <textarea
          ref={ref}
          rows={1}
          value={text}
          placeholder="Message your agent…"
          onChange={(e) => setText(e.target.value)}
          onKeyDown={onKeyDown}
        />
        {streaming ? (
          <button className="send stop" onClick={onStop} title="Stop">
            ■
          </button>
        ) : (
          <button className="send" onClick={submit} disabled={!text.trim()} title="Send">
            ↑
          </button>
        )}
      </div>
      <div className="footnote">Enter to send · Shift+Enter for a new line · chats are saved locally</div>
    </div>
  );
}

/* ---------- the whole pane ---------- */

export default function ChatView({
  title,
  chatKey,
  messages,
  streaming,
  error,
  provider,
  model,
  onSend,
  onStop,
  onToggleSidebar,
  onOpenSettings,
}) {
  const scrollRef = useRef(null);
  const stick = useRef(true); // keep pinned to the bottom unless the user scrolls up

  const onScroll = () => {
    const el = scrollRef.current;
    stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
  };

  useEffect(() => {
    const el = scrollRef.current;
    if (el && stick.current) el.scrollTop = el.scrollHeight;
  }, [messages]);

  useEffect(() => {
    stick.current = true;
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [chatKey]);

  const handleSend = (text) => {
    stick.current = true;
    onSend(text);
  };

  return (
    <main className="main">
      <header className="topbar">
        <button className="icon-btn" onClick={onToggleSidebar} title="Toggle sidebar">
          ☰
        </button>
        <div className="top-title">{title}</div>
        {provider && (
          <button className="badge" onClick={onOpenSettings} title="Change provider / model in Settings">
            {provider === 'openrouter' ? model : provider === 'http' ? 'Custom agent' : 'Echo mode'}
          </button>
        )}
      </header>

      <div className="messages" ref={scrollRef} onScroll={onScroll}>
        <div className="thread">
          {messages.length === 0 ? (
            <div className="empty">
              <h1>What are we working on?</h1>
              <p>Chat with your agent. Every conversation is saved on this machine.</p>
              {provider === 'echo' && (
                <p className="hint">
                  No AI connected yet, so replies are echoed.{' '}
                  <button className="link" onClick={onOpenSettings}>
                    Add your OpenRouter API key
                  </button>{' '}
                  to start chatting.
                </p>
              )}
            </div>
          ) : (
            messages.map((m, i) => (
              <Message
                key={m.id ?? `tmp-${i}`}
                role={m.role}
                content={m.content}
                pending={streaming && m.role === 'assistant' && i === messages.length - 1}
              />
            ))
          )}
          {error && <div className="error">{error}</div>}
        </div>
      </div>

      <Composer streaming={streaming} focusKey={chatKey} onSend={handleSend} onStop={onStop} />
    </main>
  );
}
