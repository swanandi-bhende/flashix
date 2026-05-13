import { create } from 'zustand';
import {
  SystemMetrics,
  ActivityEvent,
  HealthStatus,
  PipelineState,
  RiskStatus,
  Opportunity,
  RiskCenter,
} from '@/types';

interface DashboardStore {
  metrics: SystemMetrics;
  activities: ActivityEvent[];
  loading: boolean;
  lastRefresh: Date | null;
  opportunities: Opportunity[];
  riskCenter: RiskCenter;
  // opportunity actions
  simulateOpportunity: (id: string) => Promise<'valid' | 'marginal' | 'invalid'>;
  approveOpportunity: (id: string) => void;
  rejectOpportunity: (id: string, reason: string) => void;
  getOpportunity: (id: string) => Opportunity | undefined;
  
  // Actions
  setMetrics: (metrics: SystemMetrics) => void;
  setActivities: (activities: ActivityEvent[]) => void;
  setLoading: (loading: boolean) => void;
  addActivity: (activity: ActivityEvent) => void;
  refreshData: () => Promise<void>;
  
  // Risk center actions
  acknowledgeBreaker: (breakerId: string) => void;
  acknowledgeOverride: (overrideId: string) => void;
  triggerEmergencyStop: (reason: string, by: string) => void;
  clearEmergencyStop: () => void;
}

// Mock data generator for development
const generateMockMetrics = (): SystemMetrics => ({
  pipelineState: ['idle', 'processing', 'degraded', 'halted'][Math.floor(Math.random() * 4)] as PipelineState,
  totalOpportunities: Math.floor(Math.random() * 500) + 50,
  activeOpportunities: Math.floor(Math.random() * 30) + 5,
  livePositions: Math.floor(Math.random() * 20) + 2,
  riskStatus: ['green', 'elevated', 'blocked'][Math.floor(Math.random() * 3)] as RiskStatus,
  openBreakers: Math.floor(Math.random() * 5),
  executionHealth: ['healthy', 'warning', 'critical'][Math.floor(Math.random() * 3)] as HealthStatus,
  recentExecutions: Math.floor(Math.random() * 100) + 10,
  settlementStatus: ['healthy', 'warning', 'critical'][Math.floor(Math.random() * 3)] as HealthStatus,
  marketDataFreshness: Math.floor(Math.random() * 30),
  lastMarketDataSample: new Date(Date.now() - Math.floor(Math.random() * 60000)),
});

const generateMockActivities = (): ActivityEvent[] => {
  const types: Array<'opportunity_detected' | 'risk_event' | 'execution' | 'settlement' | 'market_feed'> = [
    'opportunity_detected',
    'risk_event',
    'execution',
    'settlement',
    'market_feed',
  ];

  return Array.from({ length: 8 }, (_, i) => ({
    id: `activity-${i}`,
    type: types[i % types.length],
    timestamp: new Date(Date.now() - i * 5 * 60000),
    title: [
      'New arbitrage opportunity detected',
      'Risk threshold elevated',
      'Trade execution completed',
      'Settlement confirmed',
      'Market feed updated',
    ][i % 5],
    description: [
      'High-value opportunity on ETH/USDC pair',
      'Slippage increased beyond 0.5%',
      'Profit: $2,450 | Gas: $120',
      '5 positions settled, ledger updated',
      'Uniswap V3 feed refreshed',
    ][i % 5],
    status: ['healthy', 'warning', 'critical'][i % 3] as HealthStatus,
  }));
};

const generateMockOpportunities = (): Opportunity[] => {
  const now = Date.now();
  return Array.from({ length: 8 }, (_, i) => {
    const expected = Math.floor(Math.random() * 4000) + 200;
    const gas = Math.round(expected * 0.02) + Math.floor(Math.random() * 50);
    const flash = Math.round(expected * 0.01);
    const slippage = parseFloat((Math.random() * 0.005).toFixed(4));
    const overhead = Math.round(Math.random() * 20);
    const fees = Math.round(expected * 0.005);
    const confidence = parseFloat((Math.random() * 0.5 + 0.5).toFixed(2));

    const pair = ['ETH/USDC', 'DAI/USDC', 'WBTC/BTC', 'USDT/USDC'][i % 4];
    const sourcePrices = [
      { exchange: 'Uniswap', price: parseFloat((100 + Math.random() * 10).toFixed(4)) },
      { exchange: 'Sushi', price: parseFloat((100 + Math.random() * 10).toFixed(4)) },
    ];
    const targetPrices = [
      { exchange: 'Balancer', price: parseFloat((100 + Math.random() * 10 + 0.2).toFixed(4)) },
    ];
    const spread = parseFloat((((targetPrices[0].price - sourcePrices[0].price) / sourcePrices[0].price) * 100).toFixed(3));

    return {
      id: `OPP-${1000 + i}`,
      detectionTime: new Date(now - i * 60000),
      source: ['mempool', 'scanner', 'cost-engine'][i % 3],
      type: ['arbitrage', 'funding', 'liquidation'][i % 3],
      expectedProfit: expected,
      risk: parseFloat((Math.random() * 1.2).toFixed(2)),
      status: 'pending',
      freshnessSeconds: i * 12,
      trace: [
        { step: 'discovery', detail: 'seen in mempool', timestamp: new Date(now - i * 60000) },
        { step: 'filtering', detail: 'passed filters', timestamp: new Date(now - i * 50000) },
        { step: 'cost', detail: 'cost estimated', timestamp: new Date(now - i * 40000) },
      ],
      pair,
      sourcePrices,
      targetPrices,
      spreadPct: spread,
      gasCost: gas,
      flashloanCost: flash,
      slippageEstimate: slippage,
      executionOverhead: overhead,
      fees,
      confidenceScore: confidence,
      confidenceFactors: ['model_score', 'low_slippage', 'high_liquidity'],
      riskChecks: {
        breakerTriggered: Math.random() > 0.95,
        collateralOk: true,
        slippageLimitOk: slippage < 0.01,
        exposureOk: true,
        warnings: [],
      },
      rawPayload: {
        id: `raw-${1000 + i}`,
        metadata: { source: 'simulated', score: confidence },
      },
    } as Opportunity;
  });
};

const generateMockRiskCenter = (): RiskCenter => {
  const now = Date.now();
  return {
    overallStatus: Math.random() > 0.7 ? 'green' : Math.random() > 0.4 ? 'elevated' : 'blocked',
    breakers: [
      {
        id: 'breaker-1',
        name: 'Daily Loss',
        trigger: 'Cumulative loss exceeds $50k',
        threshold: 50000,
        current: Math.floor(Math.random() * 60000),
        status: Math.random() > 0.8 ? 'triggered' : Math.random() > 0.4 ? 'warning' : 'healthy',
        activatedAt: Math.random() > 0.7 ? new Date(now - Math.floor(Math.random() * 3600000)) : undefined,
        affectedTradeCount: Math.floor(Math.random() * 10),
      },
      {
        id: 'breaker-2',
        name: 'Slippage',
        trigger: 'Single trade slippage > 1%',
        threshold: 1,
        current: parseFloat((Math.random() * 1.5).toFixed(2)),
        status: Math.random() > 0.85 ? 'warning' : 'healthy',
        affectedTradeCount: Math.floor(Math.random() * 5),
      },
      {
        id: 'breaker-3',
        name: 'Exposure',
        trigger: 'Concurrent position > $5M',
        threshold: 5000000,
        current: Math.floor(Math.random() * 6000000),
        status: 'healthy',
      },
    ],
    limits: {
      dailyLossLimit: 50000,
      currentDailyLoss: Math.floor(Math.random() * 60000),
      collateralRatio: 2.5,
      collateralLimit: 2.0,
      maxConcurrentPositions: 20,
      currentPositions: Math.floor(Math.random() * 22),
      slippageLimitPct: 1,
      currentSlippagePct: parseFloat((Math.random() * 0.8).toFixed(2)),
    },
    positions: [
      { id: 'pos-1', tradeName: 'ETH/USDC Arb', exposureSize: 250000, entryTime: new Date(now - 3600000), currentState: 'active', affectsBreakerIds: ['breaker-1'], affectsLimits: [] },
      { id: 'pos-2', tradeName: 'DAI/USDC Arb', exposureSize: 180000, entryTime: new Date(now - 7200000), currentState: 'active', affectsLimits: [] },
      { id: 'pos-3', tradeName: 'WBTC/BTC Arb', exposureSize: 420000, entryTime: new Date(now - 1800000), currentState: 'at_risk', affectsBreakerIds: ['breaker-3'] },
    ],
    overrides: [
      { id: 'override-1', triggeredBy: 'admin@flashix.com', triggeredAt: new Date(now - 7200000), reason: 'Manual override for maintenance', active: false, pausesTrading: true },
    ],
    lastUpdated: new Date(),
  };
};

export const useDashboardStore = create<DashboardStore>((set, get) => ({
  metrics: generateMockMetrics(),
  activities: generateMockActivities(),
  opportunities: generateMockOpportunities(),
  riskCenter: generateMockRiskCenter(),
  loading: false,
  lastRefresh: new Date(),

  setMetrics: (metrics) => set({ metrics }),
  setActivities: (activities) => set({ activities }),
  setLoading: (loading) => set({ loading }),
  
  addActivity: (activity) => set((state) => ({
    activities: [activity, ...state.activities].slice(0, 10),
  })),

  // Opportunity actions
  simulateOpportunity: async (id: string) => {
    // simulate a pre-flight check (mock)
    await new Promise((r) => setTimeout(r, 400));
    const outcome = Math.random();
    const result: 'valid' | 'marginal' | 'invalid' = outcome > 0.7 ? 'valid' : outcome > 0.4 ? 'marginal' : 'invalid';
    set((state) => ({
      opportunities: state.opportunities.map((o) => (o.id === id ? { ...o, simulatedResult: result } : o)),
    }));
    return result;
  },

  approveOpportunity: (id: string) => set((state) => ({
    opportunities: state.opportunities.map((o) => (o.id === id ? { ...o, status: 'executing' } : o)),
  })),

  rejectOpportunity: (id: string, reason: string) => set((state) => ({
    opportunities: state.opportunities.map((o) => (o.id === id ? { ...o, status: 'rejected', rejectionReason: reason } : o)),
  })),

  getOpportunity: (id: string) => {
    const s = get();
    return s.opportunities.find((o: Opportunity) => o.id === id);
  },

  refreshData: async () => {
    set({ loading: true });
    try {
      // Simulate API call
      await new Promise((resolve) => setTimeout(resolve, 500));
      
      set({
        metrics: generateMockMetrics(),
        activities: generateMockActivities(),
        lastRefresh: new Date(),
        loading: false,
      });
    } catch (error) {
      console.error('Failed to refresh dashboard data:', error);
      set({ loading: false });
    }
  },

  // Risk center actions
  acknowledgeBreaker: (breakerId: string) => set((state) => ({
    riskCenter: {
      ...state.riskCenter,
      breakers: state.riskCenter.breakers.map((b) => (b.id === breakerId ? { ...b, status: 'healthy' } : b)),
    },
  })),

  acknowledgeOverride: (overrideId: string) => set((state) => ({
    riskCenter: {
      ...state.riskCenter,
      overrides: state.riskCenter.overrides.map((o) => (o.id === overrideId ? { ...o, active: false } : o)),
    },
  })),

  triggerEmergencyStop: (reason: string, by: string) => set((state) => ({
    riskCenter: {
      ...state.riskCenter,
      overallStatus: 'emergency',
      overrides: [...state.riskCenter.overrides, {
        id: `override-${Date.now()}`,
        triggeredBy: by,
        triggeredAt: new Date(),
        reason,
        active: true,
        pausesTrading: true,
      }],
    },
  })),

  clearEmergencyStop: () => set((state) => ({
    riskCenter: {
      ...state.riskCenter,
      overrides: state.riskCenter.overrides.map((o) => ({ ...o, active: false })),
    },
  })),
}));
