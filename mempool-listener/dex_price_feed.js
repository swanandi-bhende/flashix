/**
 * Live DEX Price Feed Aggregation Module
 * 
 * Maintains real-time in-memory price map for perpetual swap markets across
 * three target DEXs: Aave Perps, Hyperliquid, and dYdX.
 * 
 * Polls REST APIs at 500ms intervals for:
 * - Mark price
 * - Index price
 * - Funding rate
 * - Collateral interest rate
 * 
 * Features:
 * - Stale price detection (excludes prices older than 2 seconds)
 * - Price spread calculation between DEX pairs
 * - Error handling with detailed logging
 * - In-memory cache with last-update tracking
 */

const axios = require('axios');
const EventEmitter = require('events');

// ========== Configuration ==========
const CONFIG = {
  PRICE_REFRESH_MS: parseInt(process.env.MEMPOOL_PRICE_REFRESH_MS || '500'),
  PRICE_STALENESS_THRESHOLD_MS: 2000, // 2 seconds
  AAVE_PERPS_API: 'https://aave.com/perps/api/markets',
  HYPERLIQUID_API: 'https://api.hyperliquid.xyz/info',
  DYDX_API: 'https://api.dydx.exchange/v3/markets',
  SUPPORTED_MARKETS: ['BTC-USD-PERP', 'ETH-USD-PERP', 'ARB-USD-PERP'],
};

// ========== Price Map Storage ==========
const priceMap = new Map(); // Key: symbol, Value: { dex, markPrice, indexPrice, fundingRate, collateralRate, lastUpdated, staleness }

const priceFeedEmitter = new EventEmitter();
priceFeedEmitter.setMaxListeners(15);

let refreshIntervals = {
  aave: null,
  hyperliquid: null,
  dydx: null,
};

// ========== Logging ==========
function log(level, message, data = {}) {
  const timestamp = new Date().toISOString();
  console.log(`[${timestamp}] [DEX_PRICE] [${level}] ${message}`, data && Object.keys(data).length > 0 ? data : '');
}

// ========== Aave Perps Price Fetching ==========
async function fetchAavePerpsPrices() {
  try {
    const response = await axios.get(CONFIG.AAVE_PERPS_API, {
      timeout: 5000,
      headers: { 'Accept': 'application/json' },
    });

    // Aave API structure: response.data is array of markets
    const markets = response.data || [];
    
    for (const market of markets) {
      const symbol = market.name || market.symbol;
      if (!CONFIG.SUPPORTED_MARKETS.includes(symbol)) continue;

      const now = Date.now();
      priceMap.set(`${symbol}:aave`, {
        dex: 'aave',
        symbol,
        markPrice: parseFloat(market.markPrice || 0),
        indexPrice: parseFloat(market.indexPrice || 0),
        fundingRate: parseFloat(market.fundingRate || 0),
        collateralRate: parseFloat(market.collateralRate || 0),
        lastUpdated: now,
        staleness: false,
      });
    }

    log('DEBUG', 'Fetched Aave Perps prices', {
      marketsUpdated: markets.length,
      dex: 'aave',
    });
  } catch (err) {
    log('ERROR', 'Failed to fetch Aave Perps prices', {
      error: err.message,
      dex: 'aave',
    });
  }
}

// ========== Hyperliquid Price Fetching ==========
async function fetchHyperliquidPrices() {
  try {
    const response = await axios.post(CONFIG.HYPERLIQUID_API, 
      { type: 'allMids' },
      {
        timeout: 5000,
        headers: { 'Content-Type': 'application/json' },
      }
    );

    // Hyperliquid API returns object with market symbols as keys
    const mids = response.data || {};
    
    for (const [symbol, price] of Object.entries(mids)) {
      // Hyperliquid symbols are in format like "BTC-USD-PERP"
      if (!CONFIG.SUPPORTED_MARKETS.includes(symbol)) continue;

      const now = Date.now();
      
      // For Hyperliquid, we also need funding rate - fetch separately
      let fundingRate = 0;
      try {
        const fundingResponse = await axios.post(CONFIG.HYPERLIQUID_API,
          { type: 'fundingHistory', asset: symbol.split('-')[0] },
          { timeout: 3000 }
        );
        fundingRate = parseFloat(fundingResponse.data?.[0]?.fundingRate || 0);
      } catch (e) {
        // Continue without funding rate if fetch fails
      }

      priceMap.set(`${symbol}:hyperliquid`, {
        dex: 'hyperliquid',
        symbol,
        markPrice: parseFloat(price),
        indexPrice: parseFloat(price), // Hyperliquid doesn't distinguish
        fundingRate,
        collateralRate: 0, // Hyperliquid uses margin-based collateral
        lastUpdated: now,
        staleness: false,
      });
    }

    log('DEBUG', 'Fetched Hyperliquid prices', {
      marketsUpdated: Object.keys(mids).length,
      dex: 'hyperliquid',
    });
  } catch (err) {
    log('ERROR', 'Failed to fetch Hyperliquid prices', {
      error: err.message,
      dex: 'hyperliquid',
    });
  }
}

// ========== dYdX Price Fetching ==========
async function fetchDydxPrices() {
  try {
    const response = await axios.get(CONFIG.DYDX_API, {
      timeout: 5000,
      headers: { 'Accept': 'application/json' },
    });

    // dYdX API structure: response.data.markets is object with market IDs
    const markets = response.data?.markets || {};
    
    for (const [marketId, market] of Object.entries(markets)) {
      const symbol = market.indexToken?.symbol + '-USD-PERP';
      if (!CONFIG.SUPPORTED_MARKETS.includes(symbol)) continue;

      const now = Date.now();
      priceMap.set(`${symbol}:dydx`, {
        dex: 'dydx',
        symbol,
        markPrice: parseFloat(market.oraclePrice || 0),
        indexPrice: parseFloat(market.oraclePrice || 0),
        fundingRate: parseFloat(market.fundingRate || 0),
        collateralRate: 0, // dYdX uses margin-based collateral
        lastUpdated: now,
        staleness: false,
      });
    }

    log('DEBUG', 'Fetched dYdX prices', {
      marketsUpdated: Object.keys(markets).length,
      dex: 'dydx',
    });
  } catch (err) {
    log('ERROR', 'Failed to fetch dYdX prices', {
      error: err.message,
      dex: 'dydx',
    });
  }
}

// ========== Price Staleness Detection ==========
function updateStalenessFlags() {
  const now = Date.now();
  
  for (const [key, priceEntry] of priceMap.entries()) {
    const age = now - priceEntry.lastUpdated;
    priceEntry.staleness = age > CONFIG.PRICE_STALENESS_THRESHOLD_MS;
    
    if (priceEntry.staleness) {
      log('WARN', `Price is stale (${age}ms old)`, {
        symbol: priceEntry.symbol,
        dex: priceEntry.dex,
        age,
      });
    }
  }
}

// ========== Public API: Get Price Spread ==========
function getPriceSpread(symbol, dexA, dexB) {
  const keyA = `${symbol}:${dexA}`;
  const keyB = `${symbol}:${dexB}`;
  
  const priceA = priceMap.get(keyA);
  const priceB = priceMap.get(keyB);
  
  if (!priceA) {
    log('WARN', `Price not found for ${keyA}`);
    return null;
  }
  if (!priceB) {
    log('WARN', `Price not found for ${keyB}`);
    return null;
  }
  
  // Check staleness
  if (priceA.staleness || priceB.staleness) {
    log('WARN', `Stale prices detected for spread calculation`, {
      symbol,
      dexA: priceA.staleness ? '(stale)' : '(fresh)',
      dexB: priceB.staleness ? '(stale)' : '(fresh)',
    });
    return null;
  }
  
  const grossSpread = priceB.markPrice - priceA.markPrice;
  const spreadPercent = (grossSpread / priceA.markPrice) * 100;
  const fundingRateDiff = priceB.fundingRate - priceA.fundingRate;
  
  const result = {
    symbol,
    dexA,
    dexB,
    dexAPrice: priceA.markPrice,
    dexBPrice: priceB.markPrice,
    grossSpread,
    spreadPercent,
    fundingRateDiff,
    fundingRateA: priceA.fundingRate,
    fundingRateB: priceB.fundingRate,
    timestamp: Date.now(),
  };
  
  log('DEBUG', `Calculated price spread`, {
    symbol,
    dexA,
    dexB,
    spreadPercent: spreadPercent.toFixed(4) + '%',
  });
  
  return result;
}

// ========== Public API: Get Single Price ==========
function getPrice(symbol, dex) {
  const key = `${symbol}:${dex}`;
  const price = priceMap.get(key);
  
  if (!price) {
    return null;
  }
  
  if (price.staleness) {
    log('WARN', `Requested price is stale`, {
      symbol,
      dex,
      ageMs: Date.now() - price.lastUpdated,
    });
  }
  
  return price;
}

// ========== Public API: Get All Prices ==========
function getAllPrices() {
  const result = {};
  for (const [key, price] of priceMap.entries()) {
    if (!result[price.symbol]) {
      result[price.symbol] = {};
    }
    result[price.symbol][price.dex] = {
      ...price,
      age: Date.now() - price.lastUpdated,
    };
  }
  return result;
}

// ========== Public API: Start Price Feed ==========
function startPriceFeed() {
  log('INFO', 'Starting DEX price feed aggregation', {
    refreshIntervalMs: CONFIG.PRICE_REFRESH_MS,
    stalenessThresholdMs: CONFIG.PRICE_STALENESS_THRESHOLD_MS,
  });
  
  // Fetch initial prices
  fetchAavePerpsPrices();
  fetchHyperliquidPrices();
  fetchDydxPrices();
  updateStalenessFlags();
  
  // Start periodic refresh
  refreshIntervals.aave = setInterval(() => {
    fetchAavePerpsPrices();
    updateStalenessFlags();
  }, CONFIG.PRICE_REFRESH_MS);
  
  refreshIntervals.hyperliquid = setInterval(() => {
    fetchHyperliquidPrices();
    updateStalenessFlags();
  }, CONFIG.PRICE_REFRESH_MS);
  
  refreshIntervals.dydx = setInterval(() => {
    fetchDydxPrices();
    updateStalenessFlags();
  }, CONFIG.PRICE_REFRESH_MS);
}

// ========== Public API: Stop Price Feed ==========
function stopPriceFeed() {
  log('INFO', 'Stopping DEX price feed aggregation');
  
  if (refreshIntervals.aave) clearInterval(refreshIntervals.aave);
  if (refreshIntervals.hyperliquid) clearInterval(refreshIntervals.hyperliquid);
  if (refreshIntervals.dydx) clearInterval(refreshIntervals.dydx);
  
  refreshIntervals = { aave: null, hyperliquid: null, dydx: null };
}

// ========== Module Exports ==========
module.exports = {
  startPriceFeed,
  stopPriceFeed,
  getPriceSpread,
  getPrice,
  getAllPrices,
  priceFeedEmitter,
  CONFIG,
};
