/**
 * Persistent Opportunity Analytics Database
 * 
 * Stores the complete lifecycle of every opportunity the ingestion pipeline
 * processes using SQLite with better-sqlite3.
 * 
 * Features:
 * - Complete opportunity lifecycle tracking
 * - Cost breakdown persistence
 * - Status transition logging
 * - Post-trade profitability analysis
 * - Real-time analytics queries
 * - HTTP endpoint for dashboard integration
 */

const Database = require('better-sqlite3');
const path = require('path');
const fs = require('fs');

// ========== Configuration ==========
const CONFIG = {
  DB_PATH: process.env.OPPORTUNITY_DB_PATH || path.join(__dirname, '..', 'data', 'opportunities.db'),
  DB_TIMEOUT: 5000,
};

// ========== Ensure Data Directory Exists ==========
function ensureDataDirectory() {
  const dataDir = path.dirname(CONFIG.DB_PATH);
  if (!fs.existsSync(dataDir)) {
    fs.mkdirSync(dataDir, { recursive: true });
  }
}

// ========== Database Connection ==========
let db = null;

function getDb() {
  if (!db) {
    ensureDataDirectory();
    db = new Database(CONFIG.DB_PATH, {
      timeout: CONFIG.DB_TIMEOUT,
      fileMustExist: false,
    });
    db.pragma('journal_mode = WAL');
    db.pragma('synchronous = NORMAL');
  }
  return db;
}

// ========== Logging ==========
function log(level, message, data = {}) {
  const timestamp = new Date().toISOString();
  console.log(`[${timestamp}] [OPPORTUNITY_DB] [${level}] ${message}`, data && Object.keys(data).length > 0 ? data : '');
}

// ========== Initialize Database Schema ==========
function initializeDatabase() {
  const db = getDb();
  
  try {
    // Create opportunities table
    db.exec(`
      CREATE TABLE IF NOT EXISTS opportunities (
        id TEXT PRIMARY KEY,
        symbol TEXT NOT NULL,
        dex_a TEXT NOT NULL,
        dex_b TEXT NOT NULL,
        gross_spread_percent REAL,
        net_profit_percent REAL,
        opportunity_score INTEGER,
        flashloan_fee_usdc REAL,
        slippage_cost_usdc REAL,
        gas_cost_usdc REAL,
        funding_rate_cost_usdc REAL,
        total_cost_usdc REAL,
        status TEXT NOT NULL DEFAULT 'DETECTED',
        mempool_tx_hash TEXT,
        detected_at INTEGER,
        emitted_at INTEGER,
        executed_at INTEGER,
        realized_profit_usdc REAL,
        notes TEXT,
        created_at INTEGER DEFAULT (strftime('%s', 'now'))
      )
    `);
    
    // Create indices for common queries
    db.exec(`
      CREATE INDEX IF NOT EXISTS idx_opportunities_status ON opportunities(status);
      CREATE INDEX IF NOT EXISTS idx_opportunities_symbol ON opportunities(symbol);
      CREATE INDEX IF NOT EXISTS idx_opportunities_detected_at ON opportunities(detected_at);
      CREATE INDEX IF NOT EXISTS idx_opportunities_net_profit ON opportunities(net_profit_percent);
    `);
    
    log('INFO', 'Database schema initialized successfully');
  } catch (err) {
    log('ERROR', 'Failed to initialize database schema', {
      error: err.message,
      path: CONFIG.DB_PATH,
    });
    throw err;
  }
}

// ========== Insert New Opportunity ==========
function insertOpportunity(opportunity) {
  const db = getDb();
  
  try {
    const stmt = db.prepare(`
      INSERT INTO opportunities (
        id, symbol, dex_a, dex_b, gross_spread_percent, 
        net_profit_percent, opportunity_score, flashloan_fee_usdc, 
        slippage_cost_usdc, gas_cost_usdc, funding_rate_cost_usdc, 
        total_cost_usdc, status, mempool_tx_hash, detected_at, notes
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `);
    
    const result = stmt.run(
      opportunity.id,
      opportunity.symbol,
      opportunity.dexA,
      opportunity.dexB,
      opportunity.grossSpreadPercent || null,
      opportunity.netProfitPercent || null,
      opportunity.opportunityScore || null,
      opportunity.flashloanFeeUsdc || null,
      opportunity.slippageCostUsdc || null,
      opportunity.gasCostUsdc || null,
      opportunity.fundingRateCostUsdc || null,
      opportunity.totalCostUsdc || null,
      opportunity.status || 'DETECTED',
      opportunity.mempoolTxHash || null,
      opportunity.detectedAt || Date.now(),
      opportunity.notes || null
    );
    
    log('DEBUG', `Inserted opportunity into database`, {
      opportunityId: opportunity.id,
      symbol: opportunity.symbol,
      status: opportunity.status,
    });
    
    return result;
  } catch (err) {
    log('ERROR', 'Failed to insert opportunity', {
      opportunityId: opportunity.id,
      error: err.message,
    });
    throw err;
  }
}

// ========== Update Opportunity Status ==========
function updateStatus(id, status, additionalFields = {}) {
  const db = getDb();
  
  try {
    let query = `UPDATE opportunities SET status = ?`;
    const params = [status];
    
    // Add timestamp based on status
    if (status === 'EMITTED') {
      query += `, emitted_at = ?`;
      params.push(Date.now());
    } else if (status === 'EXECUTED') {
      query += `, executed_at = ?`;
      params.push(Date.now());
    }
    
    // Add any additional fields
    for (const [key, value] of Object.entries(additionalFields)) {
      query += `, ${key} = ?`;
      params.push(value);
    }
    
    query += ` WHERE id = ?`;
    params.push(id);
    
    const stmt = db.prepare(query);
    const result = stmt.run(...params);
    
    log('DEBUG', `Updated opportunity status`, {
      opportunityId: id,
      newStatus: status,
      changes: result.changes,
    });
    
    return result;
  } catch (err) {
    log('ERROR', 'Failed to update opportunity status', {
      opportunityId: id,
      status,
      error: err.message,
    });
    throw err;
  }
}

// ========== Get Opportunity by ID ==========
function getOpportunity(id) {
  const db = getDb();
  
  try {
    const stmt = db.prepare('SELECT * FROM opportunities WHERE id = ?');
    return stmt.get(id);
  } catch (err) {
    log('ERROR', 'Failed to retrieve opportunity', {
      opportunityId: id,
      error: err.message,
    });
    return null;
  }
}

// ========== Get Pass Rate (Filter Effectiveness) ==========
function getPassRate(hours = 1) {
  const db = getDb();
  
  try {
    const thresholdTime = Math.floor((Date.now() - hours * 3600000) / 1000);
    
    const emittedCount = db.prepare(
      'SELECT COUNT(*) as count FROM opportunities WHERE status = ? AND detected_at > ?'
    ).get('EMITTED', thresholdTime).count;
    
    const detectedCount = db.prepare(
      'SELECT COUNT(*) as count FROM opportunities WHERE detected_at > ?'
    ).get(thresholdTime).count;
    
    const passRate = detectedCount > 0 ? (emittedCount / detectedCount * 100).toFixed(2) : 0;
    
    return {
      hours,
      periodStart: new Date(thresholdTime * 1000).toISOString(),
      emitted: emittedCount,
      detected: detectedCount,
      passRatePercent: parseFloat(passRate),
    };
  } catch (err) {
    log('ERROR', 'Failed to calculate pass rate', {
      error: err.message,
    });
    return null;
  }
}

// ========== Get Average Net Profit by Status ==========
function getAverageNetProfit(status = 'EXECUTED') {
  const db = getDb();
  
  try {
    const result = db.prepare(
      'SELECT AVG(net_profit_percent) as avgProfit, COUNT(*) as count FROM opportunities WHERE status = ? AND net_profit_percent > 0'
    ).get(status);
    
    return {
      status,
      averageNetProfit: result.avgProfit ? parseFloat(result.avgProfit.toFixed(4)) : 0,
      opportunityCount: result.count,
    };
  } catch (err) {
    log('ERROR', 'Failed to get average net profit', {
      status,
      error: err.message,
    });
    return null;
  }
}

// ========== Get Top Opportunities by Score ==========
function getTopOpportunities(limit = 10) {
  const db = getDb();
  
  try {
    const stmt = db.prepare(`
      SELECT 
        id, symbol, dex_a, dex_b, gross_spread_percent, 
        net_profit_percent, opportunity_score, status,
        detected_at, emitted_at, executed_at, realized_profit_usdc
      FROM opportunities
      WHERE opportunity_score IS NOT NULL
      ORDER BY opportunity_score DESC
      LIMIT ?
    `);
    
    return stmt.all(limit);
  } catch (err) {
    log('ERROR', 'Failed to get top opportunities', {
      limit,
      error: err.message,
    });
    return [];
  }
}

// ========== Get Statistics Summary ==========
function getStatistics() {
  const db = getDb();
  
  try {
    // Total counts by status
    const statusCounts = db.prepare(`
      SELECT status, COUNT(*) as count FROM opportunities GROUP BY status
    `).all();
    
    // Profitability stats
    const profitStats = db.prepare(`
      SELECT 
        AVG(net_profit_percent) as avgNetProfit,
        MIN(net_profit_percent) as minNetProfit,
        MAX(net_profit_percent) as maxNetProfit,
        COUNT(*) as totalOpportunities
      FROM opportunities
      WHERE net_profit_percent IS NOT NULL
    `).get();
    
    // Cost breakdown averages
    const costStats = db.prepare(`
      SELECT
        AVG(flashloan_fee_usdc) as avgFlashloanFee,
        AVG(slippage_cost_usdc) as avgSlippage,
        AVG(gas_cost_usdc) as avgGasCost,
        AVG(total_cost_usdc) as avgTotalCost
      FROM opportunities
      WHERE total_cost_usdc IS NOT NULL
    `).get();
    
    const statistics = {
      statusCounts: statusCounts.reduce((acc, item) => {
        acc[item.status] = item.count;
        return acc;
      }, {}),
      profitability: {
        average: profitStats.avgNetProfit ? parseFloat(profitStats.avgNetProfit.toFixed(4)) : 0,
        minimum: profitStats.minNetProfit ? parseFloat(profitStats.minNetProfit.toFixed(4)) : 0,
        maximum: profitStats.maxNetProfit ? parseFloat(profitStats.maxNetProfit.toFixed(4)) : 0,
        totalOpportunities: profitStats.totalOpportunities,
      },
      averageCosts: {
        flashloan: costStats.avgFlashloanFee ? parseFloat(costStats.avgFlashloanFee.toFixed(2)) : 0,
        slippage: costStats.avgSlippage ? parseFloat(costStats.avgSlippage.toFixed(2)) : 0,
        gas: costStats.avgGasCost ? parseFloat(costStats.avgGasCost.toFixed(2)) : 0,
        total: costStats.avgTotalCost ? parseFloat(costStats.avgTotalCost.toFixed(2)) : 0,
      },
    };
    
    return statistics;
  } catch (err) {
    log('ERROR', 'Failed to get statistics', {
      error: err.message,
    });
    return null;
  }
}

// ========== Export Records to CSV ==========
function exportToCsv(filters = {}) {
  const db = getDb();
  
  try {
    let query = 'SELECT * FROM opportunities WHERE 1=1';
    const params = [];
    
    if (filters.status) {
      query += ' AND status = ?';
      params.push(filters.status);
    }
    
    if (filters.symbol) {
      query += ' AND symbol = ?';
      params.push(filters.symbol);
    }
    
    if (filters.minProfitPercent !== undefined) {
      query += ' AND net_profit_percent >= ?';
      params.push(filters.minProfitPercent);
    }
    
    query += ' ORDER BY detected_at DESC';
    
    const stmt = db.prepare(query);
    const records = stmt.all(...params);
    
    if (records.length === 0) {
      return '';
    }
    
    // Build CSV header
    const headers = Object.keys(records[0]);
    const csvHeader = headers.join(',');
    
    // Build CSV rows
    const csvRows = records.map(record =>
      headers.map(header => {
        const value = record[header];
        if (value === null) return '';
        if (typeof value === 'string' && value.includes(',')) {
          return `"${value.replace(/"/g, '""')}"`;
        }
        return value;
      }).join(',')
    );
    
    return [csvHeader, ...csvRows].join('\n');
  } catch (err) {
    log('ERROR', 'Failed to export to CSV', {
      error: err.message,
    });
    return null;
  }
}

// ========== Close Database ==========
function closeDatabase() {
  if (db) {
    db.close();
    db = null;
    log('INFO', 'Database connection closed');
  }
}

// ========== Module Exports ==========
module.exports = {
  initializeDatabase,
  insertOpportunity,
  updateStatus,
  getOpportunity,
  getPassRate,
  getAverageNetProfit,
  getTopOpportunities,
  getStatistics,
  exportToCsv,
  closeDatabase,
  CONFIG,
};
