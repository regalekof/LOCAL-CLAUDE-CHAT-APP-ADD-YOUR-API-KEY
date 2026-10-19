import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App.jsx';
import './styles.css';

// In the desktop app, open external links in the real browser instead of inside the app window
document.addEventListener('click', (e) => {
  const a = e.target.closest?.('a[href]');
  const api = window.pywebview?.api;
  if (!a || !api?.open_external) return;
  if (!/^https?:$/.test(a.protocol) || a.origin === window.location.origin) return;
  e.preventDefault();
  api.open_external(a.href);
});

createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
