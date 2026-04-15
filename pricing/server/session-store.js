'use strict';

const fs = require('fs');
const path = require('path');

const STORE_DIR = process.env.PRICING_SESSION_STORE_DIR
  ? path.resolve(process.env.PRICING_SESSION_STORE_DIR)
  : path.join(__dirname, '..', 'data');
const STORE_PATH = process.env.PRICING_SESSION_STORE_PATH
  ? path.resolve(process.env.PRICING_SESSION_STORE_PATH)
  : path.join(STORE_DIR, 'session-store.json');
const SESSION_TTL_DAYS = parsePositiveInteger(process.env.PRICING_SESSION_TTL_DAYS, 30);
const MAX_SESSIONS_PER_CLIENT = parsePositiveInteger(process.env.PRICING_SESSION_MAX_PER_CLIENT, 50);
const PRUNE_INTERVAL_MS = parsePositiveInteger(process.env.PRICING_SESSION_PRUNE_INTERVAL_MS, 12 * 60 * 60 * 1000);

let state = { clients: {} };
let pendingFlush = null;
let flushRequested = false;
let pruneTimer = null;

function parsePositiveInteger(value, fallback) {
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : fallback;
}

function compactMessages(messages) {
  if (!Array.isArray(messages) || !messages.length) return [];
  const compacted = [];
  for (const item of messages) {
    const role = String(item?.role || 'assistant');
    const content = String(item?.content || '');
    const last = compacted[compacted.length - 1];
    if (last && last.role === role && last.content === content) continue;
    compacted.push({ role, content });
  }
  return compacted;
}

function clone(value) {
  return value ? JSON.parse(JSON.stringify(value)) : value;
}

function sessionTimestamp(session = {}) {
  const updatedAt = Number(session.updatedAt || 0);
  if (Number.isFinite(updatedAt) && updatedAt > 0) return updatedAt;
  const createdAt = Number(session.ts || 0);
  return Number.isFinite(createdAt) && createdAt > 0 ? createdAt : 0;
}

function ttlCutoff(now = Date.now()) {
  return now - (SESSION_TTL_DAYS * 24 * 60 * 60 * 1000);
}

function ensureClient(clientId) {
  const key = String(clientId || 'anonymous').trim() || 'anonymous';
  if (!state.clients[key]) state.clients[key] = { sessions: [] };
  if (!Array.isArray(state.clients[key].sessions)) state.clients[key].sessions = [];
  return state.clients[key];
}

function enforceClientSessionLimit(client) {
  if (!client || !Array.isArray(client.sessions) || client.sessions.length <= MAX_SESSIONS_PER_CLIENT) return false;
  client.sessions = client.sessions
    .slice()
    .sort((left, right) => sessionTimestamp(right) - sessionTimestamp(left))
    .slice(0, MAX_SESSIONS_PER_CLIENT);
  return true;
}

function sanitizeLoadedState(now = Date.now()) {
  const cutoff = ttlCutoff(now);
  let changed = false;

  if (!state || typeof state !== 'object' || !state.clients || typeof state.clients !== 'object') {
    state = { clients: {} };
    return true;
  }

  for (const [clientId, client] of Object.entries(state.clients)) {
    const sessionList = Array.isArray(client?.sessions) ? client.sessions : [];
    if (!Array.isArray(client?.sessions)) {
      state.clients[clientId] = { sessions: [] };
      changed = true;
      continue;
    }

    const sanitizedSessions = [];
    for (const session of sessionList) {
      const timestamp = sessionTimestamp(session);
      if (timestamp && timestamp < cutoff) {
        changed = true;
        continue;
      }

      const nextSession = {
        ...session,
        messages: compactMessages(session?.messages),
        events: Array.isArray(session?.events) ? session.events.slice(-200) : [],
        sessionContext: session?.sessionContext && typeof session.sessionContext === 'object' ? session.sessionContext : null,
        workbookContext: session?.workbookContext && typeof session.workbookContext === 'object' ? session.workbookContext : null,
      };

      if (!Array.isArray(session?.messages) || nextSession.messages.length !== session.messages.length) changed = true;
      if (!Array.isArray(session?.events) || nextSession.events.length !== session.events.length) changed = true;
      if (nextSession.sessionContext !== session?.sessionContext) changed = true;
      if (nextSession.workbookContext !== session?.workbookContext) changed = true;
      sanitizedSessions.push(nextSession);
    }

    const beforeCount = sanitizedSessions.length;
    state.clients[clientId] = { sessions: sanitizedSessions };
    if (enforceClientSessionLimit(state.clients[clientId])) changed = true;
    if (beforeCount !== sessionList.length) changed = true;
  }

  return changed;
}

function ensureLoaded() {
  if (!fs.existsSync(STORE_PATH)) return;
  try {
    const raw = fs.readFileSync(STORE_PATH, 'utf8');
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed === 'object') {
      state = parsed;
      if (sanitizeLoadedState()) queueSave();
    }
  } catch (_error) {
    state = { clients: {} };
  }
}

async function persistStateToDisk() {
  await fs.promises.mkdir(STORE_DIR, { recursive: true });
  const tempPath = `${STORE_PATH}.${process.pid}.${Date.now()}.tmp`;
  const payload = JSON.stringify(state, null, 2);
  await fs.promises.writeFile(tempPath, payload, 'utf8');
  await fs.promises.rename(tempPath, STORE_PATH);
}

function queueSave() {
  flushRequested = true;
  if (pendingFlush) return pendingFlush;
  pendingFlush = (async () => {
    while (flushRequested) {
      flushRequested = false;
      await persistStateToDisk();
    }
  })().finally(() => {
    pendingFlush = null;
  });
  return pendingFlush;
}

async function flushPendingWrites() {
  if (!pendingFlush) return;
  await pendingFlush;
}

function pruneExpiredSessions(now = Date.now()) {
  const cutoff = ttlCutoff(now);
  let changed = false;

  for (const client of Object.values(state.clients)) {
    if (!Array.isArray(client?.sessions)) continue;
    const nextSessions = client.sessions.filter((session) => {
      const timestamp = sessionTimestamp(session);
      return !timestamp || timestamp >= cutoff;
    });
    if (nextSessions.length !== client.sessions.length) {
      client.sessions = nextSessions;
      changed = true;
    }
    if (enforceClientSessionLimit(client)) changed = true;
  }

  if (changed) queueSave();
  return changed;
}

function startPruneTimer() {
  if (pruneTimer || !Number.isFinite(PRUNE_INTERVAL_MS) || PRUNE_INTERVAL_MS <= 0) return;
  pruneTimer = setInterval(() => {
    pruneExpiredSessions();
  }, PRUNE_INTERVAL_MS);
  if (typeof pruneTimer.unref === 'function') pruneTimer.unref();
}

async function shutdown() {
  if (pruneTimer) {
    clearInterval(pruneTimer);
    pruneTimer = null;
  }
  await flushPendingWrites();
}

function listSessions(clientId) {
  const client = ensureClient(clientId);
  return client.sessions
    .slice()
    .sort((a, b) => sessionTimestamp(b) - sessionTimestamp(a))
    .map((session) => ({
      id: session.id,
      title: session.title,
      ts: session.ts,
      updatedAt: session.updatedAt || session.ts,
      version: Number(session.version || 1),
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
    version: 1,
    messages: [],
    events: [],
    sessionContext: null,
    workbookContext: null,
  };
  client.sessions.unshift(session);
  enforceClientSessionLimit(client);
  queueSave();
  return clone(session);
}

function touch(session) {
  session.updatedAt = Date.now();
  session.version = Number(session.version || 1) + 1;
}

function appendMessage(clientId, sessionId, message, options = {}) {
  const client = ensureClient(clientId);
  const session = client.sessions.find((item) => item.id === sessionId);
  if (!session) return null;
  if (Number.isFinite(Number(options.expectedVersion)) && Number(options.expectedVersion) !== Number(session.version || 1)) {
    return { conflict: true, session: clone(session) };
  }
  if (!Array.isArray(session.messages)) session.messages = [];
  session.messages.push({
    role: String(message?.role || 'assistant'),
    content: String(message?.content || ''),
  });
  session.messages = compactMessages(session.messages);
  if (
    session.messages.length === 1 &&
    message?.role === 'user' &&
    String(message?.content || '').trim()
  ) {
    const text = String(message.content).replace(/\n/g, ' ').trim();
    session.title = text.slice(0, 52) + (text.length > 52 ? '…' : '');
  }
  touch(session);
  queueSave();
  return clone(session);
}

function updateSessionState(clientId, sessionId, patch, options = {}) {
  const client = ensureClient(clientId);
  const session = client.sessions.find((item) => item.id === sessionId);
  if (!session) return null;
  if (Number.isFinite(Number(options.expectedVersion)) && Number(options.expectedVersion) !== Number(session.version || 1)) {
    return { conflict: true, session: clone(session) };
  }
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
  queueSave();
  return clone(session);
}

function appendEvent(clientId, sessionId, event) {
  const client = ensureClient(clientId);
  const session = client.sessions.find((item) => item.id === sessionId);
  if (!session) return null;
  if (!Array.isArray(session.events)) session.events = [];
  const now = Date.now();
  session.events.push({
    id: String(event?.id || `evt_${now}_${Math.random().toString(36).slice(2, 8)}`),
    ts: now,
    type: String(event?.type || 'event'),
    data: clone(event?.data || {}),
  });
  if (session.events.length > 200) {
    session.events = session.events.slice(-200);
  }
  touch(session);
  queueSave();
  return clone(session);
}

function deleteSession(clientId, sessionId) {
  const client = ensureClient(clientId);
  const before = client.sessions.length;
  client.sessions = client.sessions.filter((item) => item.id !== sessionId);
  if (client.sessions.length !== before) queueSave();
  return client.sessions.length !== before;
}

function clearSessions(clientId) {
  const client = ensureClient(clientId);
  client.sessions = [];
  queueSave();
}

ensureLoaded();
pruneExpiredSessions();
startPruneTimer();

module.exports = {
  listSessions,
  getSession,
  createSession,
  appendMessage,
  appendEvent,
  updateSessionState,
  deleteSession,
  clearSessions,
  flushPendingWrites,
  pruneExpiredSessions,
  shutdown,
};
