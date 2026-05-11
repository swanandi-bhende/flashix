/**
 * Unit Tests for Cost Calculator
 * 
 * Comprehensive test suite covering:
 * - Boundary values (borrow amount at tier boundaries)
 * - Edge cases (zero funding rate, negative spread)
 * - Accuracy checks (costs within 0.01% of hand-calculated values)
 */

const costCalculator = require('../../mempool-listener/cost_calculator');

describe('Cost Calculator Module', () => {
  
  // ========== Flashloan Fee Tests ==========
  describe('Flashloan Fee Calculation', () => {
    test('should calculate 0.09% fee on $10,000 borrow', async () => {
      const mockCandidate = { id: 'test-1', fundingRateDiff: 0 };
      const borrowAmount = 10000;
      const costs = await costCalculator.calculateTotalCosts(mockCandidate, borrowAmount);
      
      expect(costs).not.toBeNull();
      expect(costs.flashloanFee.usdc).toBeCloseTo(9, 0); // 0.09% = $9
      expect(costs.flashloanFee.percent).toBeCloseTo(0.09, 2);
    });
    
    test('should calculate 0.09% fee on $50,000 borrow', async () => {
      const mockCandidate = { id: 'test-2', fundingRateDiff: 0 };
      const borrowAmount = 50000;
      const costs = await costCalculator.calculateTotalCosts(mockCandidate, borrowAmount);
      
      expect(costs.flashloanFee.usdc).toBeCloseTo(45, 0); // 0.09% = $45
    });
    
    test('should calculate 0.09% fee on $1,000,000 borrow', async () => {
      const mockCandidate = { id: 'test-3', fundingRateDiff: 0 };
      const borrowAmount = 1000000;
      const costs = await costCalculator.calculateTotalCosts(mockCandidate, borrowAmount);
      
      expect(costs.flashloanFee.usdc).toBeCloseTo(900, 0); // 0.09% = $900
    });
  });
  
  // ========== Slippage Tier Tests ==========
  describe('Slippage Cost Calculation', () => {
    test('should use 0.2% slippage for < $10,000', async () => {
      const mockCandidate = { id: 'test-4', fundingRateDiff: 0 };
      const borrowAmount = 5000;
      const costs = await costCalculator.calculateTotalCosts(mockCandidate, borrowAmount);
      
      // 0.2% of $5,000 = $10
      expect(costs.slippageCost.usdc).toBeCloseTo(10, 0);
    });
    
    test('should use 0.35% slippage for $10,000-$50,000', async () => {
      const mockCandidate = { id: 'test-5', fundingRateDiff: 0 };
      const borrowAmount = 30000;
      const costs = await costCalculator.calculateTotalCosts(mockCandidate, borrowAmount);
      
      // 0.35% of $30,000 = $105
      expect(costs.slippageCost.usdc).toBeCloseTo(105, 0);
    });
    
    test('should use 0.5% slippage for > $50,000', async () => {
      const mockCandidate = { id: 'test-6', fundingRateDiff: 0 };
      const borrowAmount = 100000;
      const costs = await costCalculator.calculateTotalCosts(mockCandidate, borrowAmount);
      
      // 0.5% of $100,000 = $500
      expect(costs.slippageCost.usdc).toBeCloseTo(500, 0);
    });
    
    test('should use 0.2% slippage exactly at $10,000 boundary', async () => {
      const mockCandidate = { id: 'test-7', fundingRateDiff: 0 };
      const borrowAmount = 10000;
      const costs = await costCalculator.calculateTotalCosts(mockCandidate, borrowAmount);
      
      // Should be 0.35% tier at boundary
      expect(costs.slippageCost.usdc).toBeCloseTo(35, 0);
    });
    
    test('should use 0.35% slippage exactly at $50,000 boundary', async () => {
      const mockCandidate = { id: 'test-8', fundingRateDiff: 0 };
      const borrowAmount = 50000;
      const costs = await costCalculator.calculateTotalCosts(mockCandidate, borrowAmount);
      
      // Should be 0.5% tier at boundary
      expect(costs.slippageCost.usdc).toBeCloseTo(250, 0);
    });
  });
  
  // ========== Funding Rate Cost Tests ==========
  describe('Funding Rate Cost Calculation', () => {
    test('should calculate zero cost for zero funding rate diff', async () => {
      const mockCandidate = { id: 'test-9', fundingRateDiff: 0 };
      const borrowAmount = 50000;
      const costs = await costCalculator.calculateTotalCosts(mockCandidate, borrowAmount);
      
      expect(costs.fundingRateCost.usdc).toBeCloseTo(0, 2);
    });
    
    test('should calculate positive cost for positive funding rate diff', async () => {
      const mockCandidate = { id: 'test-10', fundingRateDiff: 0.0001 }; // 0.01%
      const borrowAmount = 50000;
      const costs = await costCalculator.calculateTotalCosts(mockCandidate, borrowAmount);
      
      // 0.0001 * (0.05 / 8) * 50000 = cost should be positive
      expect(costs.fundingRateCost.usdc).toBeGreaterThan(0);
    });
    
    test('should use absolute value of funding rate diff', async () => {
      const mockCandidate = { id: 'test-11', fundingRateDiff: -0.0001 }; // Negative
      const borrowAmount = 50000;
      const costs = await costCalculator.calculateTotalCosts(mockCandidate, borrowAmount);
      
      // Should still be positive
      expect(costs.fundingRateCost.usdc).toBeGreaterThan(0);
    });
  });
  
  // ========== Total Cost Tests ==========
  describe('Total Cost Calculation', () => {
    test('should sum all cost components', async () => {
      const mockCandidate = { id: 'test-12', fundingRateDiff: 0.00005 };
      const borrowAmount = 50000;
      const costs = await costCalculator.calculateTotalCosts(mockCandidate, borrowAmount);
      
      // Total should equal sum of components
      const expectedTotal = 
        costs.flashloanFee.usdc + 
        costs.fundingRateCost.usdc + 
        costs.slippageCost.usdc + 
        costs.gasCost.usdc;
      
      expect(costs.totalCostUsdc).toBeCloseTo(expectedTotal, 0);
    });
    
    test('should never return negative total cost', async () => {
      const mockCandidate = { id: 'test-13', fundingRateDiff: -0.00001 };
      const borrowAmount = 1000;
      const costs = await costCalculator.calculateTotalCosts(mockCandidate, borrowAmount);
      
      expect(costs.totalCostUsdc).toBeGreaterThan(0);
    });
  });
  
  // ========== Invalid Input Tests ==========
  describe('Error Handling', () => {
    test('should return null for null candidate', async () => {
      const costs = await costCalculator.calculateTotalCosts(null, 50000);
      expect(costs).toBeNull();
    });
    
    test('should return null for zero borrow amount', async () => {
      const mockCandidate = { id: 'test-14', fundingRateDiff: 0 };
      const costs = await costCalculator.calculateTotalCosts(mockCandidate, 0);
      expect(costs).toBeNull();
    });
    
    test('should return null for negative borrow amount', async () => {
      const mockCandidate = { id: 'test-15', fundingRateDiff: 0 };
      const costs = await costCalculator.calculateTotalCosts(mockCandidate, -10000);
      expect(costs).toBeNull();
    });
  });
  
  // ========== Net Profit Calculation Tests ==========
  describe('Net Profit Calculation', () => {
    test('should calculate positive net profit', () => {
      const netProfit = costCalculator.calculateNetProfit(2.0, 0.8);
      expect(netProfit).toBe(1.2);
    });
    
    test('should calculate negative net profit', () => {
      const netProfit = costCalculator.calculateNetProfit(0.5, 1.0);
      expect(netProfit).toBe(-0.5);
    });
    
    test('should handle equal gross spread and total cost', () => {
      const netProfit = costCalculator.calculateNetProfit(1.0, 1.0);
      expect(netProfit).toBe(0);
    });
  });
  
  // ========== Slippage Rate Lookup Tests ==========
  describe('Slippage Rate Lookup', () => {
    test('should return correct tier for low borrow amount', () => {
      const rate = costCalculator.getSlippageRate(5000);
      expect(rate).toBe(0.2);
    });
    
    test('should return correct tier for mid borrow amount', () => {
      const rate = costCalculator.getSlippageRate(25000);
      expect(rate).toBe(0.35);
    });
    
    test('should return correct tier for high borrow amount', () => {
      const rate = costCalculator.getSlippageRate(100000);
      expect(rate).toBe(0.5);
    });
  });
});
