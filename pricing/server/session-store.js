'use strict';

const fs = require('fs');
const path = require('path');

const STORE_DIR = path.join(__dirname, '..', 'data');
const STORE_PATH = path.join(STORE_DIR, 'session-store.json');

let state = { clients: {} };

function ensureLoaded() {
  if (!fs.existsSync(STORE_PATH)) return;
  try {
    const raw = fs.readFileSync(STORE_PATH, 'utf8');
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed === 'object' && parsed.clients && typeof parsed.clients === 'object') {
      state = parsed;
    }
  } catch (_error) {
    state = { clients: {} };
  }
}

function save() {
  fs.mkdirSync(STORE_DIR, { recursive: true });
  fs.writeFileSync(STORE_PATH, JSON.stringify(state, null, 2));
}

function ensureClient(clientId) {
  const key = String(clientId || 'anonymous').trim() || 'anonymous';
  if (!state.clients[key]) state.clients[key] = { sessions: [] };
  return state.clients[key];
}

function clone(value) {
  return value ? JSON.parse(JSON.stringify(value)) : value;
}

function listSessions(clientId) {
  const client = ensureClient(clientId);
  return client.sessions
    .slice()
    .sort((a, b) => Number(b.updatedAt || b.ts || 0) - Number(a.updatedAt || a.ts || 0))
    .map((session) => ({
      id: session.id,
      title: session.title,
      ts: session.ts,
      updatedAt: session.updatedAt || session.ts,
      messageCount: Array.isArray(session.messages) ? session.messages.length : 0,
    }));
}

function getSession(clientId, sessionId) {
  const client = ensureClient(clientId);
  const session = client.sessions.find((item) => item.id === sessionId);
  return session ? clone(session) : null;
}

function createSession(clientId, title = 'New session') {
  const client = ensureClient(clientId);
  const now = Date.now();
  const session = {
    id: `ses_${now}_${Math.random().toString(36).slice(2, 8)}`,
    title: String(title || 'New session'),
    ts: now,
    updatedAt: now,
    messages: [],
    sessionContext: null,
    workbookContext: null,
  };
  client.sessions.unshift(session);
  save();
  return clone(session);
}

function touch(session) {
  session.updatedAt = Date.now();
}

function appendMessage(clientId, sessionId, message) {
  const client = ensureClient(clientId);
  const session = client.sessions.find((item) => item.id === sessionId);
  if (!session) return null;
  if (!Array.isArray(session.messages)) session.messages = [];
  session.messages.push({
    role: String(message?.role || 'assistant'),
    content: String(message?.content || ''),
  });
  if (
    session.messages.length === 1 &&
    message?.role === 'user' &&
    String(message?.content || '').trim()
  ) {
    const text = String(message.content).replace(/\n/g, ' ').trim();
    session.title = text.slice(0, 52) + (text.length > 52 ? '…' : '');
  }
  touch(session);
  save();
  return clone(session);
}

function updateSessionState(clientId, sessionId, patch) {
  const client = ensureClient(clientId);
  const session = client.sessions.find((item) => item.id === sessionId);
  if (!session) return null;
  if (Object.prototype.hasOwnProperty.call(patch || {}, 'sessionContext')) {
    session.sessionContext = patch.sessionContext ? clone(patch.sessionContext) : null;
  }
  if (Object.prototype.hasOwnProperty.call(patch || {}, 'workbookContext')) {
    session.workbookContext = patch.workbookContext ? clone(patch.workbookContext) : null;
  }
  if (typeof patch?.title === 'string' && patch.title.trim()) {
    session.title = patch.title.trim();
  }
  touch(session);
  save();
  return clone(session);
}

function deleteSession(clientId, sessionId) {
  const client = ensureClient(clientId);
  const before = client.sessions.length;
  client.sessions = client.sessions.filter((item) => item.id !== sessionId);
  if (client.sessions.length !== before) save();
  return client.sessions.length !== before;
}

function clearSessions(clientId) {
  const client = ensureClient(clientId);
  client.sessions = [];
  save();
}

ensureLoaded();

module.exports = {
  listSessions,
  getSession,
  createSession,
  appendMessage,
  updateSessionState,
  deleteSession,
  clearSessions,
};
