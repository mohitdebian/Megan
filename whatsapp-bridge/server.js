/**
 * Megan WhatsApp Bridge — Local REST API for WhatsApp messaging.
 *
 * Uses whatsapp-web.js (headless Chrome) + Express to expose WhatsApp
 * as a private local API on port 3001.
 *
 * Endpoints:
 *   GET  /status        → connection status + QR state
 *   POST /send          → send a message { chatId, message }
 *   GET  /messages       → recent incoming messages (in-memory buffer)
 *   GET  /contacts       → search contacts by name
 *
 * Auth: LocalAuth saves session in .wwebjs_auth/ — scan QR once.
 */

const { Client, LocalAuth } = require('whatsapp-web.js');
const express = require('express');
const qrcode = require('qrcode-terminal');

const app = express();
app.use(express.json());

const PORT = 3001;
const MAX_MESSAGES = 100; // Keep last N incoming messages in memory
const MAX_SEEN_MESSAGE_IDS = 2000;

// ── State ──
let clientReady = false;
let qrCode = null;
const recentMessages = [];
const seenMessageIds = new Set();

function normalizeChatId(raw) {
  const value = String(raw || '').trim();
  if (!value) {
    return null;
  }

  // Already looks like a WhatsApp JID.
  if (value.includes('@')) {
    const lowered = value.toLowerCase();
    if (lowered.endsWith('@c.us') || lowered.endsWith('@g.us') || lowered.endsWith('@lid')) {
      return lowered;
    }
    return null;
  }

  // Default phone-number flow: keep digits only.
  const digits = value.replace(/[^0-9]/g, '');
  if (digits.length < 8) {
    return null;
  }
  return `${digits}@c.us`;
}

async function resolveSendTarget(rawChatId) {
  const normalized = normalizeChatId(rawChatId);
  if (!normalized) {
    return null;
  }

  // Known-good explicit JIDs can be sent directly.
  if (normalized.endsWith('@g.us') || normalized.endsWith('@lid')) {
    return normalized;
  }

  // For phone-like targets, prefer an exact contact id if available. This
  // avoids @c.us failures for LID-only contacts.
  try {
    const contacts = await client.getContacts();
    const bare = normalized.replace('@c.us', '');
    const exact = contacts.find((c) => String(c.number || '') === bare);
    if (exact?.id?._serialized) {
      return exact.id._serialized.toLowerCase();
    }
  } catch (err) {
    console.warn('⚠️  Contact lookup failed, falling back to @c.us:', err.message);
  }

  return normalized;
}

// ── WhatsApp Client ──
const client = new Client({
  authStrategy: new LocalAuth({
    dataPath: './.wwebjs_auth',
  }),
  puppeteer: {
    headless: true,
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-dev-shm-usage',
      '--disable-accelerated-2d-canvas',
      '--no-first-run',
      '--disable-gpu',
    ],
  },
});

// ── WhatsApp Events ──

client.on('qr', (qr) => {
  qrCode = qr;
  console.log('\n╔══════════════════════════════════════╗');
  console.log('║   SCAN THIS QR CODE WITH WHATSAPP    ║');
  console.log('╚══════════════════════════════════════╝\n');
  qrcode.generate(qr, { small: true });
});

client.on('ready', () => {
  clientReady = true;
  qrCode = null;
  console.log('\n✅ WhatsApp client is READY');
  console.log(`🌐 Bridge API running on http://localhost:${PORT}`);
  console.log('─'.repeat(45));
});

client.on('authenticated', () => {
  console.log('🔐 Authenticated (session saved)');
});

client.on('auth_failure', (msg) => {
  console.error('❌ Auth failure:', msg);
  clientReady = false;
});

client.on('disconnected', (reason) => {
  console.log('⚠️  Disconnected:', reason);
  clientReady = false;
  // Auto-reconnect
  setTimeout(() => {
    console.log('🔄 Attempting reconnect...');
    client.initialize();
  }, 5000);
});

// Store incoming messages in memory + forward to Megan backend
client.on('message', async (msg) => {
  try {
    const messageId = msg?.id?._serialized;
    if (!messageId) {
      return;
    }

    if (seenMessageIds.has(messageId)) {
      return;
    }

    seenMessageIds.add(messageId);
    if (seenMessageIds.size > MAX_SEEN_MESSAGE_IDS) {
      const oldest = seenMessageIds.values().next().value;
      if (oldest) {
        seenMessageIds.delete(oldest);
      }
    }

    const contact = await msg.getContact();
    const entry = {
      id: messageId,
      from: msg.from,
      name: contact.pushname || contact.name || msg.from,
      number: contact.number || msg.from.replace('@c.us', ''),
      body: msg.body,
      timestamp: msg.timestamp,
      type: msg.type,
      isGroup: msg.from.endsWith('@g.us'),
    };

    recentMessages.unshift(entry);
    if (recentMessages.length > MAX_MESSAGES) {
      recentMessages.pop();
    }

    console.log(`📩 ${entry.name}: ${entry.body.slice(0, 60)}${entry.body.length > 60 ? '...' : ''}`);

    // Forward to Megan backend webhook (non-blocking)
    if (!entry.isGroup) {
      fetch('http://localhost:8000/api/whatsapp-incoming', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id: entry.id,
          chatId: entry.from,
          name: entry.name,
          number: entry.number,
          body: entry.body,
          timestamp: entry.timestamp,
        }),
      }).catch(() => {}); // Silently ignore if backend is down
    }
  } catch (e) {
    // Silently ignore message processing errors
  }
});

// ── REST API Routes ──

// Health / Status
app.get('/status', (req, res) => {
  res.json({
    ready: clientReady,
    qrPending: qrCode !== null,
    messagesBuffered: recentMessages.length,
    uptime: process.uptime(),
  });
});

// Send a message
app.post('/send', async (req, res) => {
  if (!clientReady) {
    return res.status(503).json({
      success: false,
      error: 'WhatsApp client not ready. Check /status for QR code.',
    });
  }

  const { chatId, message } = req.body;

  if (!chatId || !message) {
    return res.status(400).json({
      success: false,
      error: 'Both "chatId" and "message" are required. chatId format: "919876543210@c.us"',
    });
  }

  try {
    const formattedId = await resolveSendTarget(chatId);
    if (!formattedId) {
      return res.status(400).json({
        success: false,
        error: 'Invalid chatId. Use a phone number with country code or a valid WhatsApp JID (@c.us, @g.us, @lid).',
      });
    }

    const sentMsg = await client.sendMessage(formattedId, message);
    console.log(`📤 Sent to ${formattedId}: ${message.slice(0, 60)}...`);

    res.json({
      success: true,
      messageId: sentMsg.id._serialized,
      to: formattedId,
      timestamp: sentMsg.timestamp,
    });
  } catch (err) {
    console.error('❌ Send error:', err.message);
    res.status(500).json({
      success: false,
      error: err.message,
    });
  }
});

// Get recent incoming messages
app.get('/messages', (req, res) => {
  const limit = parseInt(req.query.limit) || 20;
  const from = req.query.from; // Optional: filter by sender number

  let filtered = recentMessages;
  if (from) {
    const normalized = from.replace('+', '').replace(/\s/g, '');
    filtered = filtered.filter((m) => m.from.includes(normalized));
  }

  res.json({
    success: true,
    count: Math.min(filtered.length, limit),
    messages: filtered.slice(0, limit),
  });
});

// Search contacts by name
app.get('/contacts', async (req, res) => {
  if (!clientReady) {
    return res.status(503).json({ success: false, error: 'Client not ready' });
  }

  const query = (req.query.q || '').toLowerCase();
  if (!query) {
    return res.status(400).json({ success: false, error: 'Query parameter "q" is required' });
  }

  try {
    const contacts = await client.getContacts();
    const matches = contacts
      .filter((c) => {
        const name = (c.pushname || c.name || '').toLowerCase();
        const number = c.number || '';
        return name.includes(query) || number.includes(query);
      })
      .slice(0, 10)
      .map((c) => ({
        id: c.id._serialized,
        name: c.pushname || c.name || 'Unknown',
        number: c.number,
        isGroup: c.isGroup,
      }));

    res.json({ success: true, count: matches.length, contacts: matches });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

// ── Start ──
app.listen(PORT, () => {
  console.log('╔══════════════════════════════════════╗');
  console.log('║     MEGAN WHATSAPP BRIDGE v1.0       ║');
  console.log('╚══════════════════════════════════════╝');
  console.log(`\n🚀 API server on http://localhost:${PORT}`);
  console.log('⏳ Initializing WhatsApp client...\n');
  client.initialize();
});
