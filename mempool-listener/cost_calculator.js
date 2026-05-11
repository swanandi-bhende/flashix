/**
 * Multi-Factor Cost Calculation Engine
 * 
 * Computes precise, conservative net profit estimates for arbitrage opportunities.
 * Breaks down costs into four components:
 * 1. Flashloan Fee (0.09% from LendingPool.sol)
 * 2. Funding Rate Cost (per 8-hour epoch)
 * 3. Slippage Cost (tiered by borrow amount)
 * 4. Gas Cost (0G Chain gas + conversion to USDC)
 * 
 * Features:
 * - Detailed cost breakdown for transparency
 * - Tiered slippage model based on trade size
 * - Conservative gas estimation (180,000 units)
 * - Logging of all cost calculations
 */

const { ethers } = require('ethers');

// ========== Configuration ==========
const CONFIG = {
  FLASHLOAN_FEE_BPS: 9, // 0.09% from LendingPool.sol
  FUNDING_RATE_HOLDING_PERIOD_HOURS: 0.05, // 3 minutes = ~0.05 hours
  FUNDING_RATE_EPOCH_HOURS: 8, // Funding rates charged per 8-hour epoch
  GAS_UNITS_FULL_CYCLE: 180000, // From ArbitrageExecutor.sol profiling
  
  // Slippage tiers (in percent)
  SLIPPAGE_TIERS: [
    { maxAmount: 10000, slippagePercent: 0.2 },
    { maxAmount: 50000, slippagePercent: 0.35 },
    { maxAmount: Infinity, slippagePercent: 0.5 },
  ],
  
  // RPC endpoint for gas price data
  RPC_PROVIDER: process.env.RPC_PROVIDER || 'https://eth-mainnet.g.alchemy.com/v2/demo',
  ETH_USDC_ORACLE_PRICE: parseFloat(process.env.ETH_USDC_PRICE || '2500'), // Fallback price
};

// ========== Logging ==========
function log(level, message, data = {}) {
  const timestamp = new Date().toISOString();
  console.log(`[${timestamp}] [COST_CALCULATOR] [${level}] ${message}`, data && Object.keys(data).length > 0 ? data : '');
}

// ========== Get Slippage Rate by Amount ==========
function getSlippageRate(borrowAmountUsdc) {
  for (const tier of CONFIG.SLIPPAGE_TIERS) {
    if (borrowAmountUsdc <= tier.maxAmount) {
      return tier.slippagePercent;
    }
  }
  return CONFIG.SLIPPAGE_TIERS[CONFIG.SLIPPAGE_TIERS.length - 1].slippagePercent;
}

// ========== Fetch Current Gas Price ==========
let cachedGasPrice = null;
let lastGasPriceFetch = 0;

async function getGasPrice() {
  const now = Date.now();
  
  // Cache gas price for 5 seconds to avoid spamming RPC
  if (cachedGasPrice && (now - lastGasPriceFetch) < 5000) {
    return cachedGasPrice;
  }
  
  try {
    const provider = new ethers.JsonRpcProvider(CONFIG.RPC_PROVIDER);
    const feeData = await provider.getFeeData();
    
    if (feeData && feeData.gasPrice) {
      cachedGasPrice = feeData.gasPrice;
      lastGasPriceFetch = now;
      
      log('DEBUG', 'Fetched current gas price', {
        gasPriceWei: feeData.gasPrice.toString(),
        gasPriceGwei: ethers.formatUnits(feeData.gasPrice, 'gwei'),
      });
      
      return feeData.gasPrice;
    }
  } catch (err) {
    log('WARN', 'Failed to fetch gas price from RPC, using fallback', {
      error: err.message,
      fallbackGweiPrice: 25, // 25 gwei fallback
    });
    return ethers.parseUnits('25', 'gwei');
  }
}

// ========== Calculate Flashloan Fee ==========
function calculateFlashloanFee(borrowAmountUsdc) {
  const feeBps = CONFIG.FLASHLOAN_FEE_BPS;
  const fee = borrowAmountUsdc * (feeBps / 10000);
  
  return {
    feeBps,
    borrowAmount: borrowAmountUsdc,
    feeUsdc: fee,
  };
}

// ========== Calculate Funding Rate Cost ==========
function calculateFundingRateCost(borrowAmountUsdc, fundingRateDiff) {
  // Funding rate is typically quoted annually; we need to adjust for our holding period
  const holdingPeriodHours = CONFIG.FUNDING_RATE_HOLDING_PERIOD_HOURS;
  const epochHours = CONFIG.FUNDING_RATE_EPOCH_HOURS;
  
  // Cost = borrowAmount * |fundingRate| * (holdingPeriod / epochPeriod)
  const costUsdc = borrowAmountUsdc * Math.abs(fundingRateDiff) * (holdingPeriodHours / epochHours);
  
  return {
    holdingPeriodHours,
    epochHours,
    fundingRateDiff,
    costUsdc,
  };
}

// ========== Calculate Slippage Cost ==========
function calculateSlippageCost(borrowAmountUsdc) {
  const slippageRate = getSlippageRate(borrowAmountUsdc);
  const slippageCostUsdc = borrowAmountUsdc * (slippageRate / 100);
  
  return {
    borrowAmount: borrowAmountUsdc,
    slippageRate: slippageRate.toFixed(2) + '%',
    slippageCostUsdc,
  };
}

// ========== Calculate Gas Cost ==========
async function calculateGasCost(ethUsdcPrice = CONFIG.ETH_USDC_ORACLE_PRICE) {
  try {
    const gasPrice = await getGasPrice();
    
    // Convert gas price to gwei for calculation
    const gasPriceGwei = parseFloat(ethers.formatUnits(gasPrice, 'gwei'));
    
    // Total gas in Wei = gasUnits * gasPriceWei
    const totalGasWei = BigInt(CONFIG.GAS_UNITS_FULL_CYCLE) * gasPrice;
    
    // Convert Wei to ETH
    const gasEth = parseFloat(ethers.formatUnits(totalGasWei, 18));
    
    // Convert ETH to USDC using oracle price
    const gasCostUsdc = gasEth * ethUsdcPrice;
    
    return {
      gasUnits: CONFIG.GAS_UNITS_FULL_CYCLE,
      gasPriceGwei: gasPriceGwei.toFixed(2),
      gasEth: gasEth.toFixed(6),
      ethUsdcPrice,
      gasCostUsdc,
    };
  } catch (err) {
    log('ERROR', 'Failed to calculate gas cost', {
      error: err.message,
    });
    
    // Fallback calculation
    const fallbackGasPrice = 25; // gwei
    const gasEth = (CONFIG.GAS_UNITS_FULL_CYCLE * fallbackGasPrice) / 1e9;
    const gasCostUsdc = gasEth * ethUsdcPrice;
    
    return {
      gasUnits: CONFIG.GAS_UNITS_FULL_CYCLE,
      gasPriceGwei: fallbackGasPrice,
      gasEth: gasEth.toFixed(6),
      ethUsdcPrice,
      gasCostUsdc,
      fallback: true,
    };
  }
}

// ========== Main Cost Calculation Function ==========
async function calculateTotalCosts(candidate, borrowAmountUsdc) {
  if (!candidate) {
    log('ERROR', 'Cannot calculate costs: candidate is null');
    return null;
  }
  
  if (borrowAmountUsdc <= 0) {
    log('ERROR', 'Cannot calculate costs: invalid borrow amount', {
      borrowAmount: borrowAmountUsdc,
    });
    return null;
  }
  
  try {
    // Calculate each cost component
    const flashloanFee = calculateFlashloanFee(borrowAmountUsdc);
    const fundingRateCost = calculateFundingRateCost(borrowAmountUsdc, candidate.fundingRateDiff);
    const slippageCost = calculateSlippageCost(borrowAmountUsdc);
    const gasCost = await calculateGasCost();
    
    // Sum total costs
    const totalCostUsdc = 
      flashloanFee.feeUsdc + 
      fundingRateCost.costUsdc + 
      slippageCost.slippageCostUsdc + 
      gasCost.gasCostUsdc;
    
    const totalCostPercent = (totalCostUsdc / borrowAmountUsdc) * 100;
    
    const breakdown = {
      borrowAmountUsdc,
      flashloanFee: {
        percent: (flashloanFee.feeUsdc / borrowAmountUsdc) * 100,
        usdc: flashloanFee.feeUsdc,
      },
      fundingRateCost: {
        percent: (fundingRateCost.costUsdc / borrowAmountUsdc) * 100,
        usdc: fundingRateCost.costUsdc,
      },
      slippageCost: {
        percent: (slippageCost.slippageCostUsdc / borrowAmountUsdc) * 100,
        usdc: slippageCost.slippageCostUsdc,
      },
      gasCost: {
        percent: (gasCost.gasCostUsdc / borrowAmountUsdc) * 100,
        usdc: gasCost.gasCostUsdc,
      },
      totalCostUsdc,
      totalCostPercent,
      details: {
        flashloanFee,
        fundingRateCost,
        slippageCost,
        gasCost,
      },
    };
    
    log('DEBUG', 'Calculated total costs', {
      opportunityId: candidate.id,
      borrowAmount: borrowAmountUsdc,
      totalCostPercent: totalCostPercent.toFixed(4) + '%',
      breakdown: {
        flashloan: flashloanFee.feeUsdc.toFixed(2),
        fundingRate: fundingRateCost.costUsdc.toFixed(2),
        slippage: slippageCost.slippageCostUsdc.toFixed(2),
        gas: gasCost.gasCostUsdc.toFixed(2),
      },
    });
    
    return breakdown;
  } catch (err) {
    log('ERROR', 'Error calculating total costs', {
      error: err.message,
      stack: err.stack,
    });
    return null;
  }
}

// ========== Net Profit Calculation Helper ==========
function calculateNetProfit(grossSpreadPercent, totalCostPercent) {
  return grossSpreadPercent - totalCostPercent;
}

// ========== Module Exports ==========
module.exports = {
  calculateTotalCosts,
  calculateNetProfit,
  getSlippageRate,
  getGasPrice,
  CONFIG,
};
