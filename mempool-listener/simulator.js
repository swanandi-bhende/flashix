/**
 * Synthetic Mempool Simulator
 * 
 * Generates realistic synthetic mempool events and DEX price data for
 * development, testing, and demos without requiring live provider credentials.
 * 
 * Features:
 * - Configurable price spread scenarios
 * - Pre-defined scenario scripts (high_volatility, low_volatility, etc.)
 * - Same EventEmitter interface as real ingester for transparent testing
 * - Synthetic gas price and funding rate generation
 * - 100ms interval event generation
 */

const EventEmitter = require('events');
const { v4: uuidv4 } = require('uuid');

// ========== Configuration ==========
const CONFIG = {
  SIMULATION_INTERVAL_MS: 100,
  BASE_SPREAD_PERCENT: 0.3,
  SPREAD_VOLATILITY: 0.05, // How quickly spreads revert
  FUNDING_RATE_RANGE: [-0.0001, 0.0001],
  GAS_PRICE_RANGE: [10, 50], // gwei
  BASE_PRICES: {
    'BTC-USD-PERP': 42000,
    'ETH-USD-PERP': 2200,
    'ARB-USD-PERP': 1.15,
  },
  MARKETS: ['BTC-USD-PERP', 'ETH-USD-PERP', 'ARB-USD-PERP'],
  DEXES: ['aave', 'hyperliquid', 'dydx'],
};

// ========== Scenario Types ==========
const SCENARIO_TYPES = {
  HIGH_VOLATILITY: 'high_volatility',
  LOW_VOLATILITY: 'low_volatility',
  NETWORK_CONGESTION: 'network_congestion',
  RAPID_REVERSION: 'rapid_reversion',
};

// ========== Scenario Configurations ==========
const SCENARIOS = {
  [SCENARIO_TYPES.HIGH_VOLATILITY]: {
    name: 'High Volatility Scenario',
    description: 'Frequent large spreads, good for testing execution',
    baseSpread: 1.5,
    spreadVolatility: 0.15,
    fundingRateRange: [-0.0005, 0.0005],
    gasPriceRange: [30, 50],
    opportunityFrequency: 0.8, // 80% of cycles have opportunities
  },
  [SCENARIO_TYPES.LOW_VOLATILITY]: {
    name: 'Low Volatility Scenario',
    description: 'Rare small spreads, good for testing filtering',
    baseSpread: 0.2,
    spreadVolatility: 0.02,
    fundingRateRange: [-0.00005, 0.00005],
    gasPriceRange: [10, 20],
    opportunityFrequency: 0.1, // 10% of cycles have opportunities
  },
  [SCENARIO_TYPES.NETWORK_CONGESTION]: {
    name: 'Network Congestion Scenario',
    description: 'High gas prices that make most opportunities unprofitable',
    baseSpread: 1.0,
    spreadVolatility: 0.1,
    fundingRateRange: [-0.0002, 0.0002],
    gasPriceRange: [100, 200], // Very high gas
    opportunityFrequency: 0.3,
  },
  [SCENARIO_TYPES.RAPID_REVERSION]: {
    name: 'Rapid Reversion Scenario',
    description: 'Spread opens and closes within 200ms, testing timing logic',
    baseSpread: 2.0,
    spreadVolatility: 0.3, // Revert quickly
    fundingRateRange: [-0.001, 0.001],
    gasPriceRange: [20, 40],
    opportunityFrequency: 0.9,
  },
};

// ========== Event Emitter ==========
const simulatorEmitter = new EventEmitter();
simulatorEmitter.setMaxListeners(20);

// ========== Simulation State ==========
let simulationActive = false;
let simulationInterval = null;
let currentScenario = SCENARIO_TYPES.HIGH_VOLATILITY;
let simulationStats = {
  cyclesGenerated: 0,
  opportunitiesGenerated: 0,
  txsGenerated: 0,
  startTime: null,
};

// Market state tracking for realistic price evolution
const marketState = {};

// ========== Logging ==========
function log(level, message, data = {}) {
  const timestamp = new Date().toISOString();
  console.log(`[${timestamp}] [SIMULATOR] [${level}] ${message}`, data && Object.keys(data).length > 0 ? data : '');
}

// ========== Initialize Market State ==========
function initializeMarketState() {
  for (const market of CONFIG.MARKETS) {
    for (const dex of CONFIG.DEXES) {
      const key = `${market}:${dex}`;
      marketState[key] = {
        price: CONFIG.BASE_PRICES[market],
        priceNoiseAccumulator: 0,
        spreadDirection: Math.random() > 0.5 ? 1 : -1,
      };
    }
  }
}

// ========== Generate Random Spread ==========
function generateSpread(scenario) {
  const rand = Math.random();
  
  // Generate spread with specified volatility
  if (rand < scenario.opportunityFrequency) {
    // Generate opportunity spread
    const spread = scenario.baseSpread + (Math.random() - 0.5) * scenario.spreadVolatility * 2;
    return Math.max(0.1, Math.min(5.0, spread)); // Clamp between 0.1% and 5%
  } else {
    // Generate below-threshold spread
    const spread = (Math.random() - 0.5) * scenario.baseSpread * 0.3;
    return Math.max(-0.5, Math.min(0.5, spread));
  }
}

// ========== Generate Synthetic DEX Price Pair ==========
function generatePricePair(market, scenario) {
  const basePrice = CONFIG.BASE_PRICES[market];
  const spread = generateSpread(scenario);
  
  // Create realistic price divergence
  const priceA = basePrice * (1 + (spread / 100) / 2);
  const priceB = basePrice * (1 - (spread / 100) / 2);
  
  return {
    priceA: parseFloat(priceA.toFixed(2)),
    priceB: parseFloat(priceB.toFixed(2)),
    spread,
  };
}

// ========== Generate Synthetic Funding Rates ==========
function generateFundingRates(scenario) {
  const [minRate, maxRate] = scenario.fundingRateRange;
  const rateA = minRate + Math.random() * (maxRate - minRate);
  const rateB = minRate + Math.random() * (maxRate - minRate);
  
  return {
    fundingRateA: parseFloat(rateA.toFixed(6)),
    fundingRateB: parseFloat(rateB.toFixed(6)),
  };
}

// ========== Generate Synthetic Gas Price ==========
function generateGasPrice(scenario) {
  const [minGas, maxGas] = scenario.gasPriceRange;
  return Math.round(minGas + Math.random() * (maxGas - minGas));
}

// ========== Generate Synthetic Mempool Event ==========
function generateMempoolEvent() {
  const txHash = '0x' + Array(64).fill(0).map(() => Math.floor(Math.random() * 16).toString(16)).join('');
  const sender = '0x' + Array(40).fill(0).map(() => Math.floor(Math.random() * 16).toString(16)).join('');
  
  return {
    tx_hash: txHash,
    tx_contents: {
      from: sender,
      to: '0x' + Array(40).fill(0).map(() => 'a').join(''),
      value: '0',
      data: '0x' + Array(100).fill(0).map(() => Math.floor(Math.random() * 16).toString(16)).join(''),
    },
    local_region: ['US', 'EU', 'ASIA'][Math.floor(Math.random() * 3)],
    time: Date.now(),
  };
}

// ========== Generate Full Simulation Cycle ==========
function generateSimulationCycle() {
  simulationStats.cyclesGenerated++;
  
  const scenario = SCENARIOS[currentScenario];
  
  // Generate DEX price snapshots for all markets
  const dexSnapshots = [];
  
  for (const market of CONFIG.MARKETS) {
    const pricePair = generatePricePair(market, scenario);
    const fundingRates = generateFundingRates(scenario);
    
    // Create snapshot for each DEX
    for (let i = 0; i < CONFIG.DEXES.length; i++) {
      const dex = CONFIG.DEXES[i];
      const key = `${market}:${dex}`;
      
      // Add some realistic price drift
      const driftAmount = (Math.random() - 0.5) * 0.5; // Small random drift
      const price = CONFIG.BASE_PRICES[market] + driftAmount;
      
      dexSnapshots.push({
        market,
        dex,
        price: parseFloat(price.toFixed(2)),
        fundingRate: fundingRates.fundingRateA,
        timestamp: Date.now(),
      });
    }
  }
  
  // Emit DEX snapshot event
  simulatorEmitter.emit('dex-snapshot', {
    snapshots: dexSnapshots,
    receivedAt: Date.now(),
    scenario: currentScenario,
  });
  
  // Occasionally emit mempool transactions
  if (Math.random() < 0.3) {
    const txCount = Math.floor(Math.random() * 3) + 1;
    const txs = Array(txCount).fill(0).map(() => generateMempoolEvent());
    
    simulatorEmitter.emit('mempool-txs', {
      txs,
      receivedAt: Date.now(),
    });
    
    simulationStats.txsGenerated += txCount;
  }
  
  log('DEBUG', `Generated simulation cycle ${simulationStats.cyclesGenerated}`, {
    scenario: currentScenario,
    dexSnapshotsCount: dexSnapshots.length,
    txsGenerated: simulationStats.txsGenerated,
  });
}

// ========== Start Simulator ==========
function startSimulator(scenario = SCENARIO_TYPES.HIGH_VOLATILITY) {
  if (simulationActive) {
    log('WARN', 'Simulator is already running');
    return;
  }
  
  if (!SCENARIOS[scenario]) {
    log('ERROR', `Unknown scenario: ${scenario}`);
    return;
  }
  
  currentScenario = scenario;
  simulationActive = true;
  simulationStats.startTime = Date.now();
  
  initializeMarketState();
  
  log('INFO', `Starting mempool simulator (${SCENARIOS[scenario].name})`, {
    scenario,
    description: SCENARIOS[scenario].description,
    interval: CONFIG.SIMULATION_INTERVAL_MS,
  });
  
  // Emit initial connected event
  simulatorEmitter.emit('connected', {
    simulationMode: true,
    scenario,
  });
  
  // Start periodic simulation cycles
  simulationInterval = setInterval(() => {
    generateSimulationCycle();
  }, CONFIG.SIMULATION_INTERVAL_MS);
}

// ========== Stop Simulator ==========
function stopSimulator() {
  if (!simulationActive) {
    log('WARN', 'Simulator is not running');
    return;
  }
  
  simulationActive = false;
  if (simulationInterval) {
    clearInterval(simulationInterval);
    simulationInterval = null;
  }
  
  const uptime = (Date.now() - simulationStats.startTime) / 1000;
  log('INFO', 'Stopped mempool simulator', {
    uptimeSeconds: uptime.toFixed(2),
    cyclesGenerated: simulationStats.cyclesGenerated,
    opportunitiesGenerated: simulationStats.opportunitiesGenerated,
    txsGenerated: simulationStats.txsGenerated,
  });
}

// ========== Switch Scenario at Runtime ==========
function switchScenario(newScenario) {
  if (!SCENARIOS[newScenario]) {
    log('ERROR', `Unknown scenario: ${newScenario}`);
    return;
  }
  
  const oldScenario = currentScenario;
  currentScenario = newScenario;
  
  log('INFO', `Switched scenario`, {
    fromScenario: oldScenario,
    toScenario: newScenario,
    newDescription: SCENARIOS[newScenario].description,
  });
  
  simulatorEmitter.emit('scenario-switch', {
    fromScenario: oldScenario,
    toScenario: newScenario,
  });
}

// ========== Get Simulator Status ==========
function getSimulatorStatus() {
  return {
    active: simulationActive,
    currentScenario,
    scenarioConfig: SCENARIOS[currentScenario],
    stats: {
      ...simulationStats,
      uptimeSeconds: simulationStats.startTime ? (Date.now() - simulationStats.startTime) / 1000 : 0,
    },
    availableScenarios: Object.keys(SCENARIOS),
  };
}

// ========== Module Exports ==========
module.exports = {
  startSimulator,
  stopSimulator,
  switchScenario,
  getSimulatorStatus,
  simulatorEmitter,
  SCENARIO_TYPES,
  SCENARIOS,
  CONFIG,
};
