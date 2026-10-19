const JSON_HEADERS = { 'Content-Type': 'application/json' };

async function parse(res) {
  if (!res.ok) throw new Error(`${res.status} ${(await res.text()).slice(0, 200)}`);
  return res.json();
}

export const getHealth = () => fetch('/api/health').then(parse);
export const listChats = () => fetch('/api/chats').then(parse);
export const getChat = (id) => fetch(`/api/chats/${id}`).then(parse);
export const createChat = () =>
  fetch('/api/chats', { method: 'POST', headers: JSON_HEADERS, body: '{}' }).then(parse);
export const renameChat = (id, title) =>
  fetch(`/api/chats/${id}`, { method: 'PATCH', headers: JSON_HEADERS, body: JSON.stringify({ title }) }).then(parse);
export const deleteChat = (id) => fetch(`/api/chats/${id}`, { method: 'DELETE' }).then(parse);
export const getSettings = () => fetch('/api/settings').then(parse);
export const saveSettings = (patch) =>
  fetch('/api/settings', { method: 'PUT', headers: JSON_HEADERS, body: JSON.stringify(patch) }).then(parse);
export const getModels = () => fetch('/api/models').then(parse);

// Sends a message and streams the reply; calls onChunk(text) for every piece that arrives.
export async function streamMessage(id, content, onChunk, signal) {
  const res = await fetch(`/api/chats/${id}/messages`, {
    method: 'POST',
    headers: JSON_HEADERS,
    body: JSON.stringify({ content }),
    signal,
  });
  if (!res.ok || !res.body) throw new Error(`${res.status} ${(await res.text()).slice(0, 200)}`);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    const text = decoder.decode(value, { stream: true });
    if (text) onChunk(text);
  }
}
