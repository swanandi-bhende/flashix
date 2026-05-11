/**
 * Core WebSocket Mempool Ingester Service
 * 
 * Establishes and maintains WebSocket connection to private mempool provider
 * (Bloxroute, Eden Network, or MEV-Relay) with robust connection lifecycle management
 * and exponential backoff reconnection logic.
 * 
 * Features:
 * - WebSocket connection with authorization header
 * - Subscribe to mempool feeds (newTxs, pendingTxs, dexSnapshots, bdnBlocks)
 * - Exponential backoff reconnection (1s, 2s, 4s, 8s, 16s, then 30s)
 * - Connection state tracking (CONNECTING, CONNECTED, RECONNECTING, FAILED)
 * - HTTP /status endpoint for health monitoring
 * - Event emission for downstream components
 * - Comprehensive logging with timestamps and stack traces
 */

require('dotenv').config();
const WebSocket = require('ws');
const express = require('express');
const EventEmitter = require('events');

// ========== Configuration ==========
const CONFIG = {
  MEMPOOL_PROVIDER: process.env.MEMPOOL_PROVIDER || 'bloxroute',
  MEMPOOL_WEBSOCKET_URL: process.env.MEMPOOL_WEBSOCKET_URL || 'wss://virginia.eth.blxrbdn.com/ws',
  MEMPOOL_API_KEY: process.env.MEMPOOL_API_KEY || '',
  MEMPOOL_SUBSCRIPTION_TOPICS: (process.env.MEMPOOL_SUBSCRIPTION_TOPICS || 'newTxs,pendingTxs,dexSnapshots').split(','),
  MEMPOOL_MODE: process.env.MEMPOOL_MODE || 'live',
  HTTP_PORT: process.env.MEMPOOL_INGESTER_PORT || 3001,
};

// ========== Connection State Machine ==========
const CONNECTION_STATES = {
  CONNECTING: 'CONNECTING',
  CONNECTED: 'CONNECTED',
  RECONNECTING: 'RECONNECTING',
  FAILED: 'FAILED',
};

// ========== Global State ==========
let connectionState = CONNECTION_STATES.CONNECTING;
let ws = null;
let reconnectAttempt = 0;
const MAX_RECONNECT_DELAY = 30000; // 30 seconds
const BASE_RECONNECT_DELAY = 1000; // 1 second
let reconnectTimer = null;
const connectionHistory = []; // Track state transitions for debugging

// ========== Event Emitter for Downstream Components ==========
const ingesterEmitter = new EventEmitter();
ingesterEmitter.setMaxListeners(20); // Allow multiple listeners

// ========== Logging Utilities ==========
function log(level, message, data = {}) {
  const timestamp = new Date().toISOString();
  const logEntry = {
    timestamp,
    level,
    message,
    ...data,
  };
  console.log(`[${timestamp}] [${level}] ${message}`, data && Object.keys(data).length > 0 ? data : '');
  
  // Record connection state transitions
  if (level === 'STATE_TRANSITION') {
    connectionHistory.push(logEntry);
    if (connectionHistory.length > 100) connectionHistory.shift(); // Keep last 100
  }
}

// ========== Connection State Tracking ==========
function setConnectionState(newState) {
  if (newState !== connectionState) {
    log('STATE_TRANSITION', `Connection state change: ${connectionState} → ${newState}`, {
      previousState: connectionState,
      newState,
      timestamp: Date.now(),
    });
    connectionState = newState;
    ingesterEmitter.emit('state-change', newState);
  }
}

// ========== WebSocket Connection Logic ==========
function connect() {
  if (CONFIG.MEMPOOL_MODE === 'simulation') {
    log('INFO', 'MEMPOOL_MODE is "simulation", ingester will use simulator instead');
    setConnectionState(CONNECTION_STATES.CONNECTED);
    ingesterEmitter.emit('connected', { simulationMode: true });
    return;
  }

  if (!CONFIG.MEMPOOL_API_KEY) {
    log('ERROR', 'MEMPOOL_API_KEY not configured in .env', {
      missingEnv: 'MEMPOOL_API_KEY',
    });
    setConnectionState(CONNECTION_STATES.FAILED);
    scheduleReconnect();
    return;
  }

  setConnectionState(CONNECTION_STATES.CONNECTING);
  log('INFO', 'Initiating WebSocket connection', {
    url: CONFIG.MEMPOOL_WEBSOCKET_URL,
    provider: CONFIG.MEMPOOL_PROVIDER,
    topics: CONFIG.MEMPOOL_SUBSCRIPTION_TOPICS,
  });

  const wsOptions = {
    headers: {
      Authorization: `${CONFIG.MEMPOOL_API_KEY}`,
    },
  };

  try {
    ws = new WebSocket(CONFIG.MEMPOOL_WEBSOCKET_URL, wsOptions);

    ws.on('open', onOpen);
    ws.on('message', onMessage);
    ws.on('error', onError);
    ws.on('close', onClose);
  } catch (err) {
    log('ERROR', 'Failed to create WebSocket', {
      error: err.message,
      stack: err.stack,
    });
    setConnectionState(CONNECTION_STATES.FAILED);
    scheduleReconnect();
  }
}

function onOpen() {
  log('INFO', 'WebSocket connection established', {
    connectedAt: Date.now(),
  });
  setConnectionState(CONNECTION_STATES.CONNECTED);
  reconnectAttempt = 0; // Reset backoff on successful connection

  // Send subscription message
  const subscriptionMessage = {
    jsonrpc: '2.0',
    id: 1,
    method: 'subscribe',
    params: [
      'newTxs',
      {
        include: ['tx_hash', 'tx_contents', 'local_region', 'time'],
      },
    ],
  };

  ws.send(JSON.stringify(subscriptionMessage), (err) => {
    if (err) {
      log('ERROR', 'Failed to send subscription message', {
        error: err.message,
      });
    } else {
      log('INFO', 'Sent subscription message', {
        topics: CONFIG.MEMPOOL_SUBSCRIPTION_TOPICS,
      });
    }
  });

  ingesterEmitter.emit('connected', {
    connectedAt: Date.now(),
    provider: CONFIG.MEMPOOL_PROVIDER,
  });
}

function onMessage(data) {
  try {
    const payload = JSON.parse(data);

    // Route to appropriate handler based on feed type
    if (payload.result && payload.result.txs) {
      // newTxs feed
      log('DEBUG', 'Received mempool transactions', {
        txCount: payload.result.txs.length,
        messageId: payload.id,
      });
      ingesterEmitter.emit('mempool-txs', {
        txs: payload.result.txs,
        receivedAt: Date.now(),
      });
    } else if (payload.result && payload.result.dexSnapshots) {
      // dexSnapshots feed
      log('DEBUG', 'Received DEX liquidity snapshot', {
        snapshotCount: payload.result.dexSnapshots.length,
        messageId: payload.id,
      });
      ingesterEmitter.emit('dex-snapshot', {
        snapshots: payload.result.dexSnapshots,
        receivedAt: Date.now(),
      });
    } else if (payload.result && payload.result.blocks) {
      // bdnBlocks feed
      log('DEBUG', 'Received BDN block', {
        blockNumber: payload.result.blocks[0]?.blockNumber,
        messageId: payload.id,
      });
      ingesterEmitter.emit('bdn-block', {
        blocks: payload.result.blocks,
        receivedAt: Date.now(),
      });
    } else {
      // Unknown payload type
      log('DEBUG', 'Received unknown payload type', {
        payloadKeys: Object.keys(payload),
        messageId: payload.id,
      });
    }
  } catch (err) {
    log('ERROR', 'Failed to parse mempool message', {
      error: err.message,
      dataLength: data.length,
      stack: err.stack,
    });
  }
}

function onError(err) {
  log('ERROR', 'WebSocket error occurred', {
    error: err.message,
    code: err.code,
    stack: err.stack,
  });
  setConnectionState(CONNECTION_STATES.FAILED);
  ingesterEmitter.emit('error', err);
  scheduleReconnect();
}

function onClose(code, reason) {
  log('INFO', 'WebSocket connection closed', {
    code,
    reason: reason.toString(),
    closedAt: Date.now(),
  });
  setConnectionState(CONNECTION_STATES.RECONNECTING);
  scheduleReconnect();
}

// ========== Exponential Backoff Reconnection ==========
function scheduleReconnect() {
  if (reconnectTimer) clearTimeout(reconnectTimer);

  let delayMs;
  if (reconnectAttempt < 5) {
    // Exponential backoff: 1s, 2s, 4s, 8s, 16s
    delayMs = BASE_RECONNECT_DELAY * Math.pow(2, reconnectAttempt);
  } else {
    // Cap at 30s
    delayMs = MAX_RECONNECT_DELAY;
  }

  log('INFO', `Scheduling reconnection`, {
    attempt: reconnectAttempt + 1,
    delayMs,
    nextRetryAt: new Date(Date.now() + delayMs).toISOString(),
  });

  reconnectTimer = setTimeout(() => {
    reconnectAttempt++;
    connect();
  }, delayMs);
}

// ========== Express HTTP Status Endpoint ==========
const app = express();

app.get('/status', (req, res) => {
  res.json({
    status: connectionState,
    provider: CONFIG.MEMPOOL_PROVIDER,
    mode: CONFIG.MEMPOOL_MODE,
    connectedAt: connectionState === CONNECTION_STATES.CONNECTED ? Date.now() : null,
    reconnectAttempt,
    websocketUrl: CONFIG.MEMPOOL_WEBSOCKET_URL,
    stateHistory: connectionHistory.slice(-20), // Last 20 transitions
  });
});

app.get('/health', (req, res) => {
  const isHealthy = connectionState === CONNECTION_STATES.CONNECTED || CONFIG.MEMPOOL_MODE === 'simulation';
  res.status(isHealthy ? 200 : 503).json({
    healthy: isHealthy,
    state: connectionState,
  });
});

// ========== Metrics Endpoint ==========
let messageStats = {
  totalReceived: 0,
  totalByType: {
    'mempool-txs': 0,
    'dex-snapshot': 0,
    'bdn-block': 0,
  },
};

ingesterEmitter.on('mempool-txs', () => {
  messageStats.totalReceived++;
  messageStats.totalByType['mempool-txs']++;
});

ingesterEmitter.on('dex-snapshot', () => {
  messageStats.totalReceived++;
  messageStats.totalByType['dex-snapshot']++;
});

ingesterEmitter.on('bdn-block', () => {
  messageStats.totalReceived++;
  messageStats.totalByType['bdn-block']++;
});

app.get('/metrics', (req, res) => {
  res.json({
    ...messageStats,
    connectionState,
    uptime: process.uptime(),
  });
});

// ========== Main Initialization ==========
function startIngester() {
  log('INFO', 'Starting Mempool Ingester Service', {
    version: '1.0.0',
    provider: CONFIG.MEMPOOL_PROVIDER,
    mode: CONFIG.MEMPOOL_MODE,
  });

  // Start HTTP server
  const server = app.listen(CONFIG.HTTP_PORT, () => {
    log('INFO', `HTTP status server listening on port ${CONFIG.HTTP_PORT}`, {
      port: CONFIG.HTTP_PORT,
      endpoints: ['/status', '/health', '/metrics'],
    });
  });

  // Graceful shutdown
  process.on('SIGTERM', () => {
    log('INFO', 'Received SIGTERM, shutting down gracefully');
    if (ws) ws.close();
    if (reconnectTimer) clearTimeout(reconnectTimer);
    server.close(() => {
      log('INFO', 'Server closed');
      process.exit(0);
    });
  });

  process.on('SIGINT', () => {
    log('INFO', 'Received SIGINT, shutting down gracefully');
    if (ws) ws.close();
    if (reconnectTimer) clearTimeout(reconnectTimer);
    server.close(() => {
      log('INFO', 'Server closed');
      process.exit(0);
    });
  });

  // Initiate connection
  if (CONFIG.MEMPOOL_MODE === 'simulation') {
    log('INFO', 'Running in simulation mode - no live connection needed');
    setConnectionState(CONNECTION_STATES.CONNECTED);
  } else {
    connect();
  }
}

// ========== Module Exports ==========
module.exports = {
  ingesterEmitter,
  CONFIG,
  connectionState: () => connectionState,
  connect,
  scheduleReconnect,
};

// Start if run directly
if (require.main === module) {
  startIngester();
}

