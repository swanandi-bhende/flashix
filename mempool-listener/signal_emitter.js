/**
 * Signal Emitter for TEE Inference Layer
 * 
 * Receives filtered opportunities, packages them into InferenceRequest schema,
 * and forwards them via HTTP POST to the TEE client endpoint.
 * 
 * Features:
 * - Payload validation against Pydantic schema (via Zod)
 * - Queue management with concurrency control (p-queue)
 * - DEX address mapping from names to contract addresses
 * - Comprehensive logging and lifecycle tracking
 * - Graceful handling of queue overflow
 */

const axios = require('axios');
const PQueue = require('p-queue');
const { z } = require('zod');
const EventEmitter = require('events');
const filterEngineModule = require('./filter_engine');

// ========== Configuration ==========
const CONFIG = {
  TEE_INFERENCE_ENDPOINT: process.env.TEE_INFERENCE_ENDPOINT || 'http://localhost:8000/infer',
  MAX_CONCURRENT_POSITIONS: parseInt(process.env.MAX_CONCURRENT_POSITIONS || '3'),
  INFERENCE_TIMEOUT_MS: 10000,
  
  // DEX Contract Address Mapping
  // These should be configured per network and point to router/pool contracts
  DEX_ADDRESSES: {
    aave: process.env.AAVE_PERPS_CONTRACT || '0x' + 'a'.repeat(40),
    hyperliquid: process.env.HYPERLIQUID_CONTRACT || '0x' + 'b'.repeat(40),
    dydx: process.env.DYDX_CONTRACT || '0x' + 'c'.repeat(40),
  },
  
  CHAIN_ID: parseInt(process.env.CHAIN_ID || '16600'), // 0G Chain
};

// ========== Event Emitter ==========
const signalEmitterEventEmitter = new EventEmitter();
signalEmitterEventEmitter.setMaxListeners(20);

// ========== Queue for Managing Concurrent Emissions ==========
const emissionQueue = new PQueue({
  concurrency: CONFIG.MAX_CONCURRENT_POSITIONS,
  interval: 1000,
  intervalCap: CONFIG.MAX_CONCURRENT_POSITIONS,
});

// ========== Inference Request Validation Schema (Zod) ==========
// This mirrors the Pydantic schema from Python
const InferenceRequestSchema = z.object({
  opportunity_id: z.string().uuid().max(36),
  dex_a: z.string().regex(/^0x[a-fA-F0-9]{40}$/),
  dex_b: z.string().regex(/^0x[a-fA-F0-9]{40}$/),
  price_a: z.number().positive(),
  price_b: z.number().positive(),
  borrow_amount_usdc: z.number().min(10).max(1000000),
  funding_rate_a: z.number().min(-1).max(1),
  funding_rate_b: z.number().min(-1).max(1),
  timestamp: z.number().int(),
  chain_id: z.number().int(),
}).refine(
  (data) => data.dex_a.toLowerCase() !== data.dex_b.toLowerCase(),
  { message: 'dex_a and dex_b must be different' }
);

// ========== Emission Statistics ==========
let emissionStats = {
  totalEmitted: 0,
  totalQueued: 0,
  totalFailed: 0,
  totalSuccessful: 0,
  queueOverflows: 0,
  currentQueueSize: 0,
};

// ========== Logging ==========
function log(level, message, data = {}) {
  const timestamp = new Date().toISOString();
  console.log(`[${timestamp}] [SIGNAL_EMITTER] [${level}] ${message}`, data && Object.keys(data).length > 0 ? data : '');
}

// ========== Validate Payload Against Schema ==========
function validatePayload(payload) {
  try {
    const validated = InferenceRequestSchema.parse(payload);
    return { valid: true, payload: validated, error: null };
  } catch (err) {
    return {
      valid: false,
      payload: null,
      error: err.errors[0]?.message || err.message,
    };
  }
}

// ========== Build Inference Request from Opportunity ==========
function buildInferenceRequest(opportunity) {
  // Map DEX names to contract addresses
  const dexAAddress = CONFIG.DEX_ADDRESSES[opportunity.dexA];
  const dexBAddress = CONFIG.DEX_ADDRESSES[opportunity.dexB];
  
  if (!dexAAddress || !dexBAddress) {
    throw new Error(`Unknown DEX address mapping: ${opportunity.dexA} or ${opportunity.dexB}`);
  }
  
  const payload = {
    opportunity_id: opportunity.id,
    dex_a: dexAAddress.toLowerCase(),
    dex_b: dexBAddress.toLowerCase(),
    price_a: parseFloat(opportunity.dexAPrice),
    price_b: parseFloat(opportunity.dexBPrice),
    borrow_amount_usdc: parseFloat(opportunity.costBreakdown.borrowAmountUsdc),
    funding_rate_a: parseFloat(opportunity.fundingRateDiff), // Simplified - in production use actual rates
    funding_rate_b: 0, // Simplified
    timestamp: Math.floor(Date.now() / 1000),
    chain_id: CONFIG.CHAIN_ID,
  };
  
  return payload;
}

// ========== Send Signal to TEE Inference Endpoint ==========
async function sendSignalToTee(opportunity) {
  try {
    // Build inference request
    const payload = buildInferenceRequest(opportunity);
    
    // Validate payload
    const validation = validatePayload(payload);
    if (!validation.valid) {
      log('ERROR', `Payload validation failed for opportunity ${opportunity.id}`, {
        validationError: validation.error,
        payload,
      });
      return {
        success: false,
        error: `Validation failed: ${validation.error}`,
        opportunityId: opportunity.id,
      };
    }
    
    log('DEBUG', `Sending signal to TEE inference endpoint`, {
      opportunityId: opportunity.id,
      symbol: opportunity.symbol,
      payloadSize: JSON.stringify(payload).length,
      endpoint: CONFIG.TEE_INFERENCE_ENDPOINT,
    });
    
    // Send POST request to TEE
    const response = await axios.post(CONFIG.TEE_INFERENCE_ENDPOINT, payload, {
      timeout: CONFIG.INFERENCE_TIMEOUT_MS,
      headers: {
        'Content-Type': 'application/json',
      },
    });
    
    log('INFO', `✓ Signal sent successfully to TEE`, {
      opportunityId: opportunity.id,
      symbol: opportunity.symbol,
      responseStatus: response.status,
    });
    
    emissionStats.totalSuccessful++;
    
    return {
      success: true,
      opportunityId: opportunity.id,
      teeResponse: response.data,
    };
  } catch (err) {
    log('ERROR', `Failed to send signal to TEE`, {
      opportunityId: opportunity.id,
      error: err.message,
      endpoint: CONFIG.TEE_INFERENCE_ENDPOINT,
    });
    
    emissionStats.totalFailed++;
    
    return {
      success: false,
      opportunityId: opportunity.id,
      error: err.message,
    };
  }
}

// ========== Emit Signal (Main Entry Point) ==========
async function emitSignal(opportunity) {
  if (!opportunity || !opportunity.id) {
    log('ERROR', 'Cannot emit signal: opportunity is invalid');
    return null;
  }
  
  // Check queue capacity
  const queueSize = emissionQueue.pending;
  emissionStats.currentQueueSize = queueSize;
  
  if (queueSize >= CONFIG.MAX_CONCURRENT_POSITIONS) {
    log('WARN', `Queue is at capacity, dropping opportunity`, {
      opportunityId: opportunity.id,
      symbol: opportunity.symbol,
      opportunityScore: opportunity.opportunityScore,
      queueSize,
      maxCapacity: CONFIG.MAX_CONCURRENT_POSITIONS,
    });
    
    emissionStats.queueOverflows++;
    signalEmitterEventEmitter.emit('queue-overflow', {
      opportunityId: opportunity.id,
      score: opportunity.opportunityScore,
    });
    
    return null;
  }
  
  emissionStats.totalQueued++;
  
  // Add to queue with concurrency control
  try {
    const result = await emissionQueue.add(
      async () => {
        const emissionTime = Date.now();
        
        const sendResult = await sendSignalToTee(opportunity);
        
        // Log emission with complete metadata
        log('DEBUG', `Signal emission complete`, {
          opportunityId: opportunity.id,
          symbol: opportunity.symbol,
          queueDepth: emissionQueue.pending,
          payloadSize: JSON.stringify(opportunity).length,
          emissionDurationMs: Date.now() - emissionTime,
          success: sendResult.success,
        });
        
        // Update opportunity status in database (would be done by obs db module)
        signalEmitterEventEmitter.emit('signal-sent', {
          opportunityId: opportunity.id,
          status: sendResult.success ? 'EMITTED' : 'EMISSION_FAILED',
          teeResponse: sendResult.teeResponse,
        });
        
        return sendResult;
      }
    );
    
    emissionStats.totalEmitted++;
    
    return result;
  } catch (err) {
    log('ERROR', `Error queuing signal emission`, {
      opportunityId: opportunity.id,
      error: err.message,
    });
    
    return null;
  }
}

// ========== Get Emission Metrics ==========
function getEmissionMetrics() {
  return {
    ...emissionStats,
    queueSize: emissionQueue.pending,
    maxConcurrency: CONFIG.MAX_CONCURRENT_POSITIONS,
    successRate: emissionStats.totalEmitted > 0
      ? ((emissionStats.totalSuccessful / emissionStats.totalEmitted) * 100).toFixed(2)
      : 0,
  };
}

// ========== Start Signal Emitter ==========
function startSignalEmitter() {
  log('INFO', 'Starting signal emitter', {
    teeEndpoint: CONFIG.TEE_INFERENCE_ENDPOINT,
    maxConcurrency: CONFIG.MAX_CONCURRENT_POSITIONS,
    chainId: CONFIG.CHAIN_ID,
  });
  
  // Subscribe to filtered opportunities from filter engine
  filterEngineModule.filteredOpportunityEmitter.on('filtered-opportunity', async (opportunity) => {
    // Emit to TEE via queue
    const result = await emitSignal(opportunity);
  });
  
  log('INFO', 'Signal emitter listening for filtered opportunities');
}

// ========== Stop Signal Emitter ==========
function stopSignalEmitter() {
  log('INFO', 'Stopping signal emitter');
  filterEngineModule.filteredOpportunityEmitter.removeAllListeners('filtered-opportunity');
  
  // Wait for queue to drain
  return emissionQueue.onEmpty();
}

// ========== Module Exports ==========
module.exports = {
  startSignalEmitter,
  stopSignalEmitter,
  emitSignal,
  getEmissionMetrics,
  signalEmitterEventEmitter,
  buildInferenceRequest,
  validatePayload,
  CONFIG,
};
