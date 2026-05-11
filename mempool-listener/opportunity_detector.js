/**
 * Arbitrage Opportunity Detector
 * 
 * Continuously scans live price feed for perpetual swap price discrepancies
 * and emits raw arbitrage candidates when conditions are met.
 * 
 * Features:
 * - 100ms interval scanning matching mempool cadence
 * - Detects price spreads > 0.5% across DEX pairs
 * - Associates opportunities with mempool transactions when available
 * - Emits candidates to filter engine via EventEmitter
 * - Logs all raw opportunities (pre-filter) to database
 * - Generates unique UUID for each opportunity
 */

const EventEmitter = require('events');
const { v4: uuidv4 } = require('uuid');
const priceFeedModule = require('./dex_price_feed');

// ========== Configuration ==========
const CONFIG = {
  SCAN_INTERVAL_MS: parseInt(process.env.MEMPOOL_POLLING_INTERVAL_MS || '100'),
  MIN_SPREAD_THRESHOLD_PERCENT: 0.5,
  SUPPORTED_MARKETS: ['BTC-USD-PERP', 'ETH-USD-PERP', 'ARB-USD-PERP'],
  DEX_LIST: ['aave', 'hyperliquid', 'dydx'],
};

// ========== Event Emitter ==========
const opportunityEmitter = new EventEmitter();
opportunityEmitter.setMaxListeners(20);

let scanInterval = null;
let scanStats = {
  totalScans: 0,
  totalDetected: 0,
  lastScanTime: null,
};

// ========== Logging ==========
function log(level, message, data = {}) {
  const timestamp = new Date().toISOString();
  console.log(`[${timestamp}] [OPPORTUNITY_DETECTOR] [${level}] ${message}`, data && Object.keys(data).length > 0 ? data : '');
}

// ========== Generate Unique Opportunity ID ==========
function generateOpportunityId() {
  return uuidv4();
}

// ========== Get All DEX Pair Combinations ==========
function getDexPairCombinations() {
  const pairs = [];
  for (let i = 0; i < CONFIG.DEX_LIST.length; i++) {
    for (let j = i + 1; j < CONFIG.DEX_LIST.length; j++) {
      pairs.push([CONFIG.DEX_LIST[i], CONFIG.DEX_LIST[j]]);
    }
  }
  return pairs;
}

// ========== Main Opportunity Scanning Logic ==========
function scanForOpportunities() {
  const scanStartTime = Date.now();
  scanStats.totalScans++;
  
  const dexPairs = getDexPairCombinations();
  const candidates = [];
  
  for (const market of CONFIG.SUPPORTED_MARKETS) {
    for (const [dexA, dexB] of dexPairs) {
      try {
        // Get price spread between DEX pair
        const spread = priceFeedModule.getPriceSpread(market, dexA, dexB);
        
        if (!spread) {
          // getPriceSpread logs warnings for missing/stale prices
          continue;
        }
        
        // Check if spread exceeds minimum threshold
        const absSpreadPercent = Math.abs(spread.spreadPercent);
        if (absSpreadPercent > CONFIG.MIN_SPREAD_THRESHOLD_PERCENT) {
          // Determine direction: which DEX should we buy from, which to sell to
          const direction = spread.spreadPercent > 0 ? 'buy_a_sell_b' : 'buy_b_sell_a';
          
          // Create raw opportunity candidate
          const candidate = {
            id: generateOpportunityId(),
            symbol: market,
            dexA,
            dexB,
            dexAPrice: spread.dexAPrice,
            dexBPrice: spread.dexBPrice,
            grossSpreadPercent: absSpreadPercent,
            spreadDirection: direction,
            fundingRateDiff: spread.fundingRateDiff,
            fundingRateA: spread.fundingRateA,
            fundingRateB: spread.fundingRateB,
            detectedAt: Date.now(),
            mempoolTxHash: null, // Will be populated if triggered by specific tx
            scanCycleId: scanStats.totalScans,
          };
          
          candidates.push(candidate);
          scanStats.totalDetected++;
          
          log('DEBUG', `Detected raw opportunity (pre-filter)`, {
            id: candidate.id,
            symbol: market,
            pair: `${dexA} ↔ ${dexB}`,
            spreadPercent: absSpreadPercent.toFixed(4),
            direction,
          });
        }
      } catch (err) {
        log('ERROR', `Error scanning pair ${dexA}-${dexB} for ${market}`, {
          error: err.message,
        });
      }
    }
  }
  
  // Emit all candidates detected in this scan cycle
  for (const candidate of candidates) {
    opportunityEmitter.emit('candidate', candidate);
  }
  
  // Update scan timing
  const scanDurationMs = Date.now() - scanStartTime;
  scanStats.lastScanTime = scanDurationMs;
  
  if (scanDurationMs > 50) {
    log('WARN', `Scan cycle took longer than expected`, {
      scanDurationMs,
      candidatesFound: candidates.length,
    });
  }
  
  return candidates;
}

// ========== Link Opportunity to Mempool Transaction ==========
function linkMempoolTransaction(opportunityId, txHash) {
  // This would be called by the ingester when processing mempool txs
  log('DEBUG', `Linking mempool transaction to opportunity`, {
    opportunityId,
    txHash,
  });
  opportunityEmitter.emit('mempool-link', {
    opportunityId,
    txHash,
  });
}

// ========== Get Detector Statistics ==========
function getDetectorStats() {
  return {
    ...scanStats,
    totalScanCycles: scanStats.totalScans,
    detectionsPerCycle: scanStats.totalScans > 0 ? (scanStats.totalDetected / scanStats.totalScans).toFixed(2) : 0,
  };
}

// ========== Start Opportunity Detector ==========
function startDetector() {
  log('INFO', 'Starting arbitrage opportunity detector', {
    scanIntervalMs: CONFIG.SCAN_INTERVAL_MS,
    minSpreadThresholdPercent: CONFIG.MIN_SPREAD_THRESHOLD_PERCENT,
    marketsMonitored: CONFIG.SUPPORTED_MARKETS,
    dexPairCombinations: getDexPairCombinations().length,
  });
  
  // Start periodic scanning
  scanInterval = setInterval(() => {
    scanForOpportunities();
  }, CONFIG.SCAN_INTERVAL_MS);
  
  // Also do initial scan
  scanForOpportunities();
}

// ========== Stop Opportunity Detector ==========
function stopDetector() {
  log('INFO', 'Stopping arbitrage opportunity detector');
  
  if (scanInterval) {
    clearInterval(scanInterval);
    scanInterval = null;
  }
}

// ========== Module Exports ==========
module.exports = {
  startDetector,
  stopDetector,
  scanForOpportunities,
  linkMempoolTransaction,
  getDetectorStats,
  opportunityEmitter,
  CONFIG,
};
