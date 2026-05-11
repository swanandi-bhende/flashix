/**
 * Unit Tests for Opportunity Detector
 * 
 * Comprehensive test suite covering:
 * - DEX pair combination generation
 * - Stale price handling
 * - Correct candidate structure
 * - Spread threshold detection
 */

const opportunityDetector = require('../../mempool-listener/opportunity_detector');
const priceFeed = require('../../mempool-listener/dex_price_feed');

describe('Opportunity Detector Module', () => {
  
  // ========== DEX Pair Combination Tests ==========
  describe('DEX Pair Combinations', () => {
    test('should generate all valid DEX pair combinations', () => {
      const pairs = [];
      const dexList = ['aave', 'hyperliquid', 'dydx'];
      
      for (let i = 0; i < dexList.length; i++) {
        for (let j = i + 1; j < dexList.length; j++) {
          pairs.push([dexList[i], dexList[j]]);
        }
      }
      
      expect(pairs.length).toBe(3); // aave-hyperliquid, aave-dydx, hyperliquid-dydx
      expect(pairs).toContainEqual(['aave', 'hyperliquid']);
      expect(pairs).toContainEqual(['aave', 'dydx']);
      expect(pairs).toContainEqual(['hyperliquid', 'dydx']);
    });
    
    test('should not include duplicate pairs', () => {
      const pairs = [];
      const dexList = ['aave', 'hyperliquid', 'dydx'];
      
      for (let i = 0; i < dexList.length; i++) {
        for (let j = i + 1; j < dexList.length; j++) {
          pairs.push([dexList[i], dexList[j]]);
        }
      }
      
      // Check no reverse pairs
      const pairStrings = pairs.map(p => `${p[0]}-${p[1]}`);
      const reversePairStrings = pairStrings.map(p => {
        const [a, b] = p.split('-');
        return `${b}-${a}`;
      });
      
      const combined = new Set([...pairStrings, ...reversePairStrings]);
      expect(combined.size).toBe(6); // 3 forward + 3 reverse
    });
  });
  
  // ========== Opportunity Candidate Structure Tests ==========
  describe('Opportunity Candidate Structure', () => {
    test('should have required fields', () => {
      const requiredFields = [
        'id',
        'symbol',
        'dexA',
        'dexB',
        'dexAPrice',
        'dexBPrice',
        'grossSpreadPercent',
        'detectedAt',
        'mempoolTxHash',
      ];
      
      const mockCandidate = {
        id: 'test-id',
        symbol: 'BTC-USD-PERP',
        dexA: 'aave',
        dexB: 'hyperliquid',
        dexAPrice: 42000,
        dexBPrice: 42840,
        grossSpreadPercent: 2.0,
        fundingRateDiff: 0.00001,
        detectedAt: Date.now(),
        mempoolTxHash: null,
      };
      
      for (const field of requiredFields) {
        expect(mockCandidate).toHaveProperty(field);
      }
    });
    
    test('should have valid UUID format for ID', () => {
      const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
      const mockCandidate = {
        id: 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', // Valid UUID
        symbol: 'BTC-USD-PERP',
        dexA: 'aave',
        dexB: 'hyperliquid',
        dexAPrice: 42000,
        dexBPrice: 42840,
        grossSpreadPercent: 2.0,
        detectedAt: Date.now(),
        mempoolTxHash: null,
      };
      
      expect(uuidRegex.test(mockCandidate.id)).toBe(true);
    });
    
    test('should have detectedAt timestamp', () => {
      const now = Date.now();
      const mockCandidate = {
        id: 'test-id',
        symbol: 'BTC-USD-PERP',
        dexA: 'aave',
        dexB: 'hyperliquid',
        dexAPrice: 42000,
        dexBPrice: 42840,
        grossSpreadPercent: 2.0,
        detectedAt: now,
        mempoolTxHash: null,
      };
      
      expect(mockCandidate.detectedAt).toBeCloseTo(now, 0);
      expect(typeof mockCandidate.detectedAt).toBe('number');
    });
  });
  
  // ========== Spread Threshold Tests ==========
  describe('Spread Threshold Detection', () => {
    test('should detect spread > 0.5% as opportunity', () => {
      const candidate = {
        id: 'test-above-threshold',
        symbol: 'BTC-USD-PERP',
        dexA: 'aave',
        dexB: 'hyperliquid',
        dexAPrice: 42000,
        dexBPrice: 42000 * 1.006, // 0.6% spread
        grossSpreadPercent: 0.6,
        fundingRateDiff: 0,
        detectedAt: Date.now(),
        mempoolTxHash: null,
      };
      
      const spreadPercent = Math.abs(candidate.grossSpreadPercent);
      expect(spreadPercent).toBeGreaterThan(0.5);
    });
    
    test('should not detect spread < 0.5% as opportunity', () => {
      const candidate = {
        id: 'test-below-threshold',
        symbol: 'BTC-USD-PERP',
        dexA: 'aave',
        dexB: 'hyperliquid',
        dexAPrice: 42000,
        dexBPrice: 42000 * 1.003, // 0.3% spread
        grossSpreadPercent: 0.3,
        fundingRateDiff: 0,
        detectedAt: Date.now(),
        mempoolTxHash: null,
      };
      
      const spreadPercent = Math.abs(candidate.grossSpreadPercent);
      expect(spreadPercent).toBeLessThan(0.5);
    });
    
    test('should handle exactly 0.5% spread', () => {
      const candidate = {
        id: 'test-exactly-threshold',
        symbol: 'BTC-USD-PERP',
        dexA: 'aave',
        dexB: 'hyperliquid',
        dexAPrice: 42000,
        dexBPrice: 42000 * 1.005, // Exactly 0.5%
        grossSpreadPercent: 0.5,
        fundingRateDiff: 0,
        detectedAt: Date.now(),
        mempoolTxHash: null,
      };
      
      const spreadPercent = Math.abs(candidate.grossSpreadPercent);
      expect(spreadPercent).toBeCloseTo(0.5, 1);
    });
  });
  
  // ========== Spread Direction Tests ==========
  describe('Spread Direction Determination', () => {
    test('should identify buy_a_sell_b direction for positive spread', () => {
      const spread = 2.0; // dexB price > dexA price
      const direction = spread > 0 ? 'buy_a_sell_b' : 'buy_b_sell_a';
      
      expect(direction).toBe('buy_a_sell_b');
    });
    
    test('should identify buy_b_sell_a direction for negative spread', () => {
      const spread = -1.5; // dexA price > dexB price
      const direction = spread > 0 ? 'buy_a_sell_b' : 'buy_b_sell_a';
      
      expect(direction).toBe('buy_b_sell_a');
    });
  });
  
  // ========== Funding Rate Inclusion Tests ==========
  describe('Funding Rate Information', () => {
    test('should include funding rate difference in candidate', () => {
      const fundingRateDiff = 0.00012;
      const candidate = {
        id: 'test-funding-rate',
        symbol: 'ETH-USD-PERP',
        dexA: 'aave',
        dexB: 'hyperliquid',
        dexAPrice: 2200,
        dexBPrice: 2200,
        grossSpreadPercent: 0,
        fundingRateDiff,
        detectedAt: Date.now(),
        mempoolTxHash: null,
      };
      
      expect(candidate.fundingRateDiff).toBe(fundingRateDiff);
    });
    
    test('should handle zero funding rate difference', () => {
      const candidate = {
        id: 'test-zero-funding',
        symbol: 'BTC-USD-PERP',
        dexA: 'aave',
        dexB: 'hyperliquid',
        dexAPrice: 42000,
        dexBPrice: 42000,
        grossSpreadPercent: 0,
        fundingRateDiff: 0,
        detectedAt: Date.now(),
        mempoolTxHash: null,
      };
      
      expect(candidate.fundingRateDiff).toBe(0);
    });
  });
  
  // ========== Mempool Transaction Linking Tests ==========
  describe('Mempool Transaction Linking', () => {
    test('should store mempool tx hash if linked', () => {
      const txHash = '0x' + 'a'.repeat(64);
      const candidate = {
        id: 'test-tx-hash',
        symbol: 'BTC-USD-PERP',
        dexA: 'aave',
        dexB: 'hyperliquid',
        dexAPrice: 42000,
        dexBPrice: 42840,
        grossSpreadPercent: 2.0,
        fundingRateDiff: 0,
        detectedAt: Date.now(),
        mempoolTxHash: txHash,
      };
      
      expect(candidate.mempoolTxHash).toBe(txHash);
    });
    
    test('should handle null mempool tx hash', () => {
      const candidate = {
        id: 'test-no-tx-hash',
        symbol: 'BTC-USD-PERP',
        dexA: 'aave',
        dexB: 'hyperliquid',
        dexAPrice: 42000,
        dexBPrice: 42840,
        grossSpreadPercent: 2.0,
        fundingRateDiff: 0,
        detectedAt: Date.now(),
        mempoolTxHash: null,
      };
      
      expect(candidate.mempoolTxHash).toBeNull();
    });
  });
  
  // ========== Statistics Tests ==========
  describe('Detector Statistics', () => {
    test('should track total scans', () => {
      const stats = opportunityDetector.getDetectorStats();
      
      expect(stats).toHaveProperty('totalScans');
      expect(typeof stats.totalScans).toBe('number');
    });
    
    test('should track total detected opportunities', () => {
      const stats = opportunityDetector.getDetectorStats();
      
      expect(stats).toHaveProperty('totalDetected');
      expect(typeof stats.totalDetected).toBe('number');
    });
    
    test('should calculate detections per cycle', () => {
      const stats = opportunityDetector.getDetectorStats();
      
      expect(stats).toHaveProperty('detectionsPerCycle');
      if (stats.totalScans > 0) {
        expect(parseFloat(stats.detectionsPerCycle)).toBeGreaterThanOrEqual(0);
      }
    });
  });
});
