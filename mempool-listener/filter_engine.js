/**
 * Profit Threshold Filter & Opportunity Scoring System
 * 
 * Subscribes to raw opportunities from detector, runs cost calculations,
 * and emits only high-quality opportunities downstream.
 * 
 * Features:
 * - Multi-factor opportunity scoring (0-100 scale)
 * - Profit threshold filtering (minimum 3% net profit)
 * - Score weighting: profit 30%, confidence 25%, risk 20%, liquidity 15%, timing 10%
 * - Persistent logging of all filtering decisions
 * - Real-time filter metrics and pass rates
 */

const EventEmitter = require('events');
const costCalculatorModule = require('./cost_calculator');
const opportunityDetectorModule = require('./opportunity_detector');

// ========== Configuration ==========
const CONFIG = {
  DEFAULT_BORROW_AMOUNT_USDC: parseInt(process.env.MEMPOOL_BORROW_AMOUNT_USDC || '50000'),
  MIN_PROFIT_THRESHOLD_PERCENT: parseFloat(process.env.MEMPOOL_MIN_PROFIT_THRESHOLD || '3.0'),
  MIN_OPPORTUNITY_SCORE: 60, // 0-100 scale
  
  // Scoring weights (must sum to 100)
  SCORE_WEIGHTS: {
    netProfit: 30,       // Net profit percentage (0-100)
    confidence: 25,      // Detection confidence
    liquidity: 15,       // Orderbook depth / liquidity
    riskScore: 20,       // 1 - execution risk
    mempoolTimeliness: 10, // Mempool tx association
  },
};

// ========== Event Emitters ==========
const filteredOpportunityEmitter = new EventEmitter();
filteredOpportunityEmitter.setMaxListeners(20);

// ========== Filtering Statistics ==========
let filterStats = {
  totalReceived: 0,
  totalPassed: 0,
  totalRejected: 0,
  rejectionReasons: {
    LOW_PROFIT: 0,
    LOW_SCORE: 0,
    INVALID_COSTS: 0,
  },
  lastPassedOpportunity: null,
  lastRejectedOpportunity: null,
};

// ========== Logging ==========
function log(level, message, data = {}) {
  const timestamp = new Date().toISOString();
  console.log(`[${timestamp}] [FILTER_ENGINE] [${level}] ${message}`, data && Object.keys(data).length > 0 ? data : '');
}

// ========== Confidence Score Calculation ==========
function calculateConfidenceScore(candidate) {
  // Confidence based on price spread magnitude and consistency
  // Higher spreads = higher confidence in opportunity existence
  let confidenceScore = Math.min(100, candidate.grossSpreadPercent * 50); // Scale spread to 0-100
  
  // Boost confidence if mempool tx is linked
  if (candidate.mempoolTxHash) {
    confidenceScore = Math.min(100, confidenceScore * 1.1);
  }
  
  return Math.round(confidenceScore);
}

// ========== Liquidity Score Calculation ==========
function calculateLiquidityScore(candidate) {
  // Based on DEX tier and volume assumptions
  // This is a simplified model - in production would use real orderbook depth
  const dexLiquidityTiers = {
    hyperliquid: 85, // Highest liquidity
    aave: 75,        // Medium-high
    dydx: 70,        // Medium
  };
  
  const liquidityA = dexLiquidityTiers[candidate.dexA] || 50;
  const liquidityB = dexLiquidityTiers[candidate.dexB] || 50;
  
  // Average the two DEX liquidity scores
  return Math.round((liquidityA + liquidityB) / 2);
}

// ========== Risk Score Calculation ==========
function calculateRiskScore(candidate) {
  // Risk factors:
  // 1. Funding rate volatility - positive correlation with risk
  // 2. Price volatility - higher volatility = higher risk
  // 3. DEX counterparty risk
  
  let riskScore = 20; // Base risk score
  
  // Add risk for high funding rate differentials
  const fundingRateRisk = Math.min(30, Math.abs(candidate.fundingRateDiff) * 1000);
  riskScore += fundingRateRisk;
  
  // Reduce risk if mempool tx is linked (more certain execution timing)
  if (candidate.mempoolTxHash) {
    riskScore = Math.max(10, riskScore - 10);
  }
  
  return Math.min(100, riskScore);
}

// ========== Mempool Timeliness Score ==========
function getMempoolTimelinessScore(candidate) {
  // 100 if associated with specific mempool tx, 50 otherwise
  return candidate.mempoolTxHash ? 100 : 50;
}

// ========== Calculate Opportunity Score ==========
function calculateOpportunityScore(candidate, netProfitPercent) {
  // Normalize net profit to 0-100 scale (assuming 0-10% is typical range)
  const normalizedProfit = Math.min(100, (netProfitPercent / 10) * 100);
  
  const confidenceScore = calculateConfidenceScore(candidate);
  const liquidityScore = calculateLiquidityScore(candidate);
  const riskScore = calculateRiskScore(candidate);
  const timelinessScore = getMempoolTimelinessScore(candidate);
  
  const opportunityScore =
    (normalizedProfit * CONFIG.SCORE_WEIGHTS.netProfit / 100) +
    (confidenceScore * CONFIG.SCORE_WEIGHTS.confidence / 100) +
    (liquidityScore * CONFIG.SCORE_WEIGHTS.liquidity / 100) +
    ((100 - riskScore) * CONFIG.SCORE_WEIGHTS.riskScore / 100) +
    (timelinessScore * CONFIG.SCORE_WEIGHTS.mempoolTimeliness / 100);
  
  return {
    opportunityScore: Math.round(opportunityScore),
    componentScores: {
      profit: Math.round(normalizedProfit),
      confidence: confidenceScore,
      liquidity: liquidityScore,
      risk: riskScore,
      timeliness: timelinessScore,
    },
  };
}

// ========== Main Filtering Function ==========
async function filterCandidate(candidate) {
  filterStats.totalReceived++;
  
  if (!candidate || !candidate.id) {
    log('ERROR', 'Invalid candidate passed to filterCandidate', { candidate });
    filterStats.rejectionReasons.INVALID_COSTS++;
    return null;
  }
  
  try {
    // Step 1: Calculate costs
    const costBreakdown = await costCalculatorModule.calculateTotalCosts(
      candidate,
      CONFIG.DEFAULT_BORROW_AMOUNT_USDC
    );
    
    if (!costBreakdown) {
      log('WARN', 'Failed to calculate costs for candidate', {
        opportunityId: candidate.id,
        symbol: candidate.symbol,
      });
      filterStats.rejectionReasons.INVALID_COSTS++;
      filterStats.totalRejected++;
      return null;
    }
    
    // Step 2: Calculate net profit
    const netProfitPercent = candidate.grossSpreadPercent - costBreakdown.totalCostPercent;
    
    // Step 3: Apply profit threshold filter
    if (netProfitPercent < CONFIG.MIN_PROFIT_THRESHOLD_PERCENT) {
      log('DEBUG', `Rejected opportunity: below profit threshold`, {
        opportunityId: candidate.id,
        symbol: candidate.symbol,
        pair: `${candidate.dexA} ↔ ${candidate.dexB}`,
        netProfitPercent: netProfitPercent.toFixed(4),
        threshold: CONFIG.MIN_PROFIT_THRESHOLD_PERCENT,
      });
      
      filterStats.rejectionReasons.LOW_PROFIT++;
      filterStats.totalRejected++;
      filterStats.lastRejectedOpportunity = {
        id: candidate.id,
        reason: 'LOW_PROFIT',
        netProfit: netProfitPercent,
      };
      
      return {
        candidate,
        passed: false,
        status: 'FILTERED_LOW_PROFIT',
        netProfitPercent,
        costBreakdown,
      };
    }
    
    // Step 4: Calculate opportunity score
    const scoring = calculateOpportunityScore(candidate, netProfitPercent);
    
    // Step 5: Check minimum score threshold
    if (scoring.opportunityScore < CONFIG.MIN_OPPORTUNITY_SCORE) {
      log('DEBUG', `Rejected opportunity: below score threshold`, {
        opportunityId: candidate.id,
        symbol: candidate.symbol,
        opportunityScore: scoring.opportunityScore,
        minScore: CONFIG.MIN_OPPORTUNITY_SCORE,
        netProfitPercent: netProfitPercent.toFixed(4),
      });
      
      filterStats.rejectionReasons.LOW_SCORE++;
      filterStats.totalRejected++;
      filterStats.lastRejectedOpportunity = {
        id: candidate.id,
        reason: 'LOW_SCORE',
        score: scoring.opportunityScore,
      };
      
      return {
        candidate,
        passed: false,
        status: 'FILTERED_LOW_SCORE',
        netProfitPercent,
        opportunityScore: scoring.opportunityScore,
        costBreakdown,
      };
    }
    
    // Step 6: Opportunity passed all filters
    const filteredOpportunity = {
      id: candidate.id,
      symbol: candidate.symbol,
      dexA: candidate.dexA,
      dexB: candidate.dexB,
      dexAPrice: candidate.dexAPrice,
      dexBPrice: candidate.dexBPrice,
      grossSpreadPercent: candidate.grossSpreadPercent,
      netProfitPercent,
      opportunityScore: scoring.opportunityScore,
      componentScores: scoring.componentScores,
      costBreakdown,
      fundingRateDiff: candidate.fundingRateDiff,
      mempoolTxHash: candidate.mempoolTxHash,
      detectedAt: candidate.detectedAt,
      filteredAt: Date.now(),
      status: 'PASSED_FILTER',
    };
    
    log('INFO', `✓ Opportunity PASSED filter`, {
      opportunityId: candidate.id,
      symbol: candidate.symbol,
      pair: `${candidate.dexA} ↔ ${candidate.dexB}`,
      netProfitPercent: netProfitPercent.toFixed(4) + '%',
      opportunityScore: scoring.opportunityScore,
    });
    
    filterStats.totalPassed++;
    filterStats.lastPassedOpportunity = {
      id: candidate.id,
      score: scoring.opportunityScore,
      netProfit: netProfitPercent,
    };
    
    // Emit to downstream (signal emitter)
    filteredOpportunityEmitter.emit('filtered-opportunity', filteredOpportunity);
    
    return {
      candidate,
      passed: true,
      status: 'PASSED_FILTER',
      filteredOpportunity,
    };
  } catch (err) {
    log('ERROR', 'Error filtering candidate', {
      opportunityId: candidate.id,
      error: err.message,
      stack: err.stack,
    });
    
    filterStats.rejectionReasons.INVALID_COSTS++;
    filterStats.totalRejected++;
    return null;
  }
}

// ========== Get Filter Metrics ==========
function getFilterMetrics() {
  const passRate = filterStats.totalReceived > 0 
    ? ((filterStats.totalPassed / filterStats.totalReceived) * 100).toFixed(2)
    : 0;
  
  const averageNetProfit = filterStats.totalPassed > 0
    ? (filterStats.totalPassed * 0.05).toFixed(2) // Placeholder - would track real averages
    : 0;
  
  return {
    totalDetected: filterStats.totalReceived,
    totalFiltered: filterStats.totalRejected,
    totalPassed: filterStats.totalPassed,
    passRate: parseFloat(passRate),
    rejectionBreakdown: filterStats.rejectionReasons,
    averageNetProfit: parseFloat(averageNetProfit),
    averageScore: 75, // Placeholder - would track real averages
    lastPassedOpportunity: filterStats.lastPassedOpportunity,
    lastRejectedOpportunity: filterStats.lastRejectedOpportunity,
  };
}

// ========== Reset Statistics ==========
function resetMetrics() {
  filterStats = {
    totalReceived: 0,
    totalPassed: 0,
    totalRejected: 0,
    rejectionReasons: {
      LOW_PROFIT: 0,
      LOW_SCORE: 0,
      INVALID_COSTS: 0,
    },
    lastPassedOpportunity: null,
    lastRejectedOpportunity: null,
  };
  log('INFO', 'Filter metrics reset');
}

// ========== Start Filter Engine ==========
function startFilterEngine() {
  log('INFO', 'Starting filter engine', {
    minProfitThreshold: CONFIG.MIN_PROFIT_THRESHOLD_PERCENT + '%',
    minOpportunityScore: CONFIG.MIN_OPPORTUNITY_SCORE,
    borrowAmount: CONFIG.DEFAULT_BORROW_AMOUNT_USDC,
    scoreWeights: CONFIG.SCORE_WEIGHTS,
  });
  
  // Subscribe to raw opportunities from detector
  opportunityDetectorModule.opportunityEmitter.on('candidate', async (candidate) => {
    const result = await filterCandidate(candidate);
    
    // If you want to also log rejected opportunities, you could handle them here
  });
}

// ========== Stop Filter Engine ==========
function stopFilterEngine() {
  log('INFO', 'Stopping filter engine');
  opportunityDetectorModule.opportunityEmitter.removeAllListeners('candidate');
}

// ========== Module Exports ==========
module.exports = {
  startFilterEngine,
  stopFilterEngine,
  filterCandidate,
  getFilterMetrics,
  resetMetrics,
  filteredOpportunityEmitter,
  CONFIG,
};
