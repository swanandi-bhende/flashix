import { create } from 'zustand';
import {
  SystemMetrics,
  ActivityEvent,
  HealthStatus,
  PipelineState,
  RiskStatus,
  Opportunity,
  RiskCenter,
  ExecutionCenter,
  BroadcastState,
  OnChainOutcome,
  SettlementCenter,
  RealizedPnL,
  PortfolioPosition,
  RepaymentStatus,
  LedgerEntry,
  MarketDataCenter,
  OracleFeedStatus,
  MarketFallbackEvent,
  MarketComparison,
  MarketDataHealthSummary,
  ComputeCenter,
  InferenceRequest,
  PayloadValidation,
  SignatureCheck,
  TraceLink,
} from '@/types';

interface DashboardStore {
  metrics: SystemMetrics;
  activities: ActivityEvent[];
  loading: boolean;
  lastRefresh: Date | null;
  opportunities: Opportunity[];
  riskCenter: RiskCenter;
  executionCenter: ExecutionCenter;
  marketDataCenter: MarketDataCenter;
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

  // Execution center actions
  runSimulation: (executionId: string) => Promise<void>;
  broadcastTrade: (executionId: string) => Promise<void>;
  retryExecution: (executionId: string) => Promise<void>;
  updateBroadcastState: (executionId: string, state: BroadcastState) => void;
  updateOnChainOutcome: (executionId: string, outcome: OnChainOutcome) => void;
  getExecution: (executionId: string) => ExecutionCenter;

  // Settlement center state and actions
  settlementCenter: SettlementCenter;
  closePosition: (positionId: string) => void;
  recordRepayment: (repaymentId: string, amount: number) => void;
  generateLedgerExport: (timeRange: { start: Date; end: Date }) => void;
  compareExpectedVsRealized: (tradeId: string) => void;

  // Market data actions
  refreshFeeds: () => void;
  getFeedByName: (name: 'Pyth' | 'Chainlink' | 'Fallback') => OracleFeedStatus | undefined;

  // Compute and TEE center state and actions
  computeCenter: ComputeCenter;
  verifyPayload: (requestId: string) => Promise<void>;
  replayInference: (requestId: string) => Promise<void>;
  viewTrace: (requestId: string) => void;
  inspectSignature: (requestId: string) => void;
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

const generateMockMarketDataCenter = (): MarketDataCenter => {
  const now = Date.now();
  const feeds: OracleFeedStatus[] = [
    {
      id: 'pyth',
      name: 'Pyth',
      isLive: true,
      status: 'healthy',
      lastUpdate: new Date(now - 8000),
      latestPrice: 3452.18,
      priceWindowLow: 3428.11,
      priceWindowHigh: 3468.54,
      stalenessSeconds: 8,
      updateFrequencySeconds: 5,
      failureCount: 0,
      lastSuccessfulSample: new Date(now - 8000),
      acceptedDeviationPct: 0.45,
    },
    {
      id: 'chainlink',
      name: 'Chainlink',
      isLive: true,
      status: 'degraded',
      lastUpdate: new Date(now - 22000),
      latestPrice: 3450.76,
      priceWindowLow: 3427.92,
      priceWindowHigh: 3467.9,
      stalenessSeconds: 22,
      warning: 'Update cadence slower than normal',
      updateFrequencySeconds: 10,
      failureCount: 1,
      lastSuccessfulSample: new Date(now - 22000),
      acceptedDeviationPct: 0.65,
    },
    {
      id: 'fallback',
      name: 'Fallback',
      isLive: true,
      status: 'healthy',
      lastUpdate: new Date(now - 4000),
      latestPrice: 3451.9,
      priceWindowLow: 3429.4,
      priceWindowHigh: 3465.22,
      stalenessSeconds: 4,
      warning: 'Synthetic aggregator engaged during primary source drift',
      updateFrequencySeconds: 3,
      failureCount: 0,
      lastSuccessfulSample: new Date(now - 4000),
      acceptedDeviationPct: 0.8,
    },
  ];

  const fallbackEvents: MarketFallbackEvent[] = [
    {
      id: 'fallback-1',
      primarySource: 'Chainlink',
      fallbackSource: 'Fallback',
      triggeredAt: new Date(now - 900000),
      resolvedAt: new Date(now - 780000),
      triggerReason: 'Chainlink feed exceeded freshness threshold',
      durationSeconds: 120,
    },
    {
      id: 'fallback-2',
      primarySource: 'Pyth',
      fallbackSource: 'Fallback',
      triggeredAt: new Date(now - 300000),
      triggerReason: 'Pyth sample timeout during burst volatility',
    },
  ];

  const comparison: MarketComparison = {
    pythVsChainlinkPct: 0.04,
    pythVsFallbackPct: 0.02,
    chainlinkVsFallbackPct: 0.06,
    hasMaterialMismatch: false,
    trustForExecution: true,
  };

  const summary: MarketDataHealthSummary = {
    overallStatus: 'healthy',
    healthySources: 2,
    totalSources: 3,
    freshestPriceAgeSeconds: Math.min(...feeds.map((feed) => feed.stalenessSeconds)),
    acceptableFreshnessSeconds: 30,
    trustForExecution: true,
    message: 'At least two sources are healthy and prices are within the execution window.',
  };

  return {
    summary,
    feeds,
    comparison,
    fallbackEvents,
    refreshedAt: new Date(),
  };
};

const generateMockComputeCenter = (): ComputeCenter => {
  const now = Date.now();
  const statuses = ['submitted', 'validating', 'validated', 'processing', 'completed', 'failed'] as const;
  const validationStatuses = ['passed', 'failed'] as const;
  const signatureStatuses = ['verified', 'failed', 'pending'] as const;

  const inferenceRequests: InferenceRequest[] = Array.from({ length: 6 }, (_, i) => ({
    id: `INF-${5000 + i}`,
    timestamp: new Date(now - i * 60000),
    sourceOpportunityId: `OPP-${1000 + i}`,
    payload: {
      pair: ['ETH/USDC', 'DAI/USDC', 'WBTC/BTC'][i % 3],
      amount: Math.floor(Math.random() * 100000) + 10000,
      minOutput: Math.floor(Math.random() * 90000) + 5000,
      slippageBps: Math.floor(Math.random() * 100) + 10,
    },
    status: statuses[i % statuses.length],
    processingTimeMs: ['completed', 'failed'].includes(statuses[i % statuses.length]) ? Math.floor(Math.random() * 2000) + 500 : undefined,
  }));

  const validations: PayloadValidation[] = inferenceRequests.map((req, i) => ({
    requestId: req.id,
    status: validationStatuses[Math.floor(Math.random() * validationStatuses.length)],
    schemaValid: Math.random() > 0.1,
    requiredFieldsMissing: Math.random() > 0.8 ? ['amount', 'slippageBps'] : [],
    malformedInputs: Math.random() > 0.85 ? ['amount: negative value'] : [],
    rejectionReason: Math.random() > 0.85 ? 'Schema validation failed: missing required fields' : undefined,
    validatedAt: new Date(now - i * 60000 + 5000),
  }));

  const signatures: SignatureCheck[] = inferenceRequests.map((req, i) => ({
    requestId: req.id,
    signerIdentity: `signer-${Math.random().toString(36).substring(2, 11)}`,
    signatureStatus: signatureStatuses[Math.floor(Math.random() * signatureStatuses.length)],
    verificationResult: Math.random() > 0.1,
    mismatchWarning: Math.random() > 0.9 ? 'Signer key rotation detected' : undefined,
    verifiedAt: Math.random() > 0.2 ? new Date(now - i * 60000 + 10000) : undefined,
  }));

  const traces: TraceLink[] = inferenceRequests.filter((_, i) => i < 4).map((req, i) => ({
    requestId: req.id,
    opportunityId: req.sourceOpportunityId,
    traceId: `TRACE-${Math.random().toString(36).substring(2, 11).toUpperCase()}`,
    linkedDecisionRecord: {
      decision: 'execute',
      confidence: parseFloat((Math.random() * 0.5 + 0.5).toFixed(2)),
      timestamp: new Date(now - i * 60000 + 15000),
    },
    downstreamConsumer: ['execution_engine', 'settlement_monitor'][i % 2],
    linkedStage: ['execution', 'settlement'][i % 2],
  }));

  return {
    inferenceRequests,
    validations,
    signatures,
    traces,
    overallHealth: Math.random() > 0.2 ? 'green' : Math.random() > 0.1 ? 'elevated' : 'blocked',
    lastUpdated: new Date(),
  };
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

const generateMockExecutionCenter = (): ExecutionCenter => {
  const now = Date.now();
  const states: Array<'awaiting_simulation' | 'simulated' | 'queued_broadcast' | 'broadcasting' | 'confirmed' | 'failed' | 'partial_success'> = [
    'awaiting_simulation',
    'simulated',
    'queued_broadcast',
    'broadcasting',
    'confirmed',
    'failed',
  ];
  const currentState = states[Math.floor(Math.random() * states.length)];
  const txHash = `0x${Math.random().toString(16).substring(2).padEnd(64, '0')}`;
  
  return {
    id: `exec-${Math.random().toString(36).substring(2, 9)}`,
    opportunityId: `opp-${Math.random().toString(36).substring(2, 9)}`,
    currentState,
    simulation: {
      id: `sim-${Math.random().toString(36).substring(2, 9)}`,
      status: ['pending', 'success', 'failed'][Math.floor(Math.random() * 3)] as 'pending' | 'success' | 'failed',
      pass: Math.random() > 0.2,
      expectedOutput: `${(Math.random() * 100).toFixed(4)} USDC`,
      expectedAmount: Math.random() * 100000,
      warnings: Math.random() > 0.6 ? ['High slippage detected', 'Low liquidity pool'] : [],
      gasEstimatedUnits: Math.floor(Math.random() * 500000) + 100000,
      executedAt: new Date(now - Math.floor(Math.random() * 300000)),
    },
    gasEstimate: {
      gasUsageUnits: Math.floor(Math.random() * 500000) + 100000,
      gasPriceWei: Math.floor(Math.random() * 100) + 20,
      totalFeeUSD: parseFloat((Math.random() * 500 + 50).toFixed(2)),
      totalFeeETH: parseFloat((Math.random() * 0.5 + 0.05).toFixed(4)),
      profitAfterGasUSD: parseFloat((Math.random() * 5000 + 500).toFixed(2)),
      profitMarginPct: parseFloat((Math.random() * 10 + 1).toFixed(2)),
      remainsProfitable: Math.random() > 0.2,
    },
    broadcastState: {
      status: currentState === 'awaiting_simulation' ? 'not_sent' : currentState === 'queued_broadcast' ? 'submitted' : currentState === 'broadcasting' ? 'pending' : 'mined',
      transactionHash: ['confirmed', 'partial_success'].includes(currentState) ? txHash : undefined,
      submittedAt: ['broadcasting', 'confirmed', 'partial_success'].includes(currentState) ? new Date(now - Math.floor(Math.random() * 300000)) : undefined,
      minedAt: ['confirmed', 'partial_success'].includes(currentState) ? new Date(now - Math.floor(Math.random() * 60000)) : undefined,
      blockNumber: ['confirmed', 'partial_success'].includes(currentState) ? Math.floor(Math.random() * 20000000) + 19000000 : undefined,
      confirmations: ['confirmed', 'partial_success'].includes(currentState) ? Math.floor(Math.random() * 50) + 1 : undefined,
    },
    onChainOutcome: {
      status: currentState === 'confirmed' ? 'success' : currentState === 'failed' ? 'reverted' : 'pending',
      blockNumber: ['confirmed', 'partial_success'].includes(currentState) ? Math.floor(Math.random() * 20000000) + 19000000 : undefined,
      transactionIndex: ['confirmed', 'partial_success'].includes(currentState) ? Math.floor(Math.random() * 100) : undefined,
      gasUsedActual: ['confirmed', 'partial_success'].includes(currentState) ? Math.floor(Math.random() * 500000) + 100000 : undefined,
      actualOutput: ['confirmed', 'partial_success'].includes(currentState) ? Math.random() * 100000 : undefined,
      errorReason: currentState === 'failed' ? 'Insufficient output amount' : undefined,
      settledAt: ['confirmed', 'partial_success'].includes(currentState) ? new Date(now - Math.floor(Math.random() * 60000)) : undefined,
    },
    lastUpdated: new Date(),
  };
};

const generateMockSettlementCenter = (): SettlementCenter => {
  const now = Date.now();
  const realizedPnLList: RealizedPnL[] = [
    {
      tradeId: 'trade-1',
      symbol: 'ETH/USDC',
      plannedProfit: 2500,
      actualGasCost: 120,
      actualProfit: 2380,
      realizationTime: new Date(now - 300000),
      status: 'completed',
    },
    {
      tradeId: 'trade-2',
      symbol: 'DAI/USDC',
      plannedProfit: 1800,
      actualGasCost: 95,
      actualProfit: 1705,
      realizationTime: new Date(now - 600000),
      status: 'completed',
    },
    {
      tradeId: 'trade-3',
      symbol: 'USDT/USDC',
      plannedProfit: 950,
      actualGasCost: 85,
      actualProfit: 865,
      realizationTime: new Date(now - 900000),
      status: 'completed',
    },
  ];

  const openPositions: PortfolioPosition[] = [
    {
      id: 'pos-1',
      tradeId: 'trade-pending-1',
      symbol: 'WBTC/BTC',
      size: 0.25,
      entryTime: new Date(now - 1800000),
      entryPrice: 42500,
      currentMark: 43200,
      exposure: 10800,
      unrealizedPnL: 175,
      status: 'active',
    },
    {
      id: 'pos-2',
      tradeId: 'trade-pending-2',
      symbol: 'AAVE/USDC',
      size: 5,
      entryTime: new Date(now - 3600000),
      entryPrice: 280,
      currentMark: 285,
      exposure: 1425,
      unrealizedPnL: 25,
      status: 'active',
    },
  ];

  const repaymentStatuses: RepaymentStatus[] = [
    {
      id: 'repay-1',
      obligationType: 'flashloan',
      amount: 50000,
      borrowedAt: new Date(now - 300000),
      repaidAmount: 50000,
      status: 'completed',
      linkedExecutionId: 'exec-1',
    },
    {
      id: 'repay-2',
      obligationType: 'settlement_fee',
      amount: 125,
      borrowedAt: new Date(now - 1800000),
      dueDate: new Date(now + 86400000),
      repaidAmount: 0,
      status: 'pending',
      linkedExecutionId: 'exec-2',
    },
  ];

  const ledgerEntries: LedgerEntry[] = [
    {
      id: 'led-1',
      tradeId: 'trade-1',
      amount: 2380,
      timestamp: new Date(now - 300000),
      entryType: 'profit',
      balanceAfter: 102380,
      description: 'ETH/USDC arb execution settled',
      linkedSettlement: 'exec-1',
    },
    {
      id: 'led-2',
      tradeId: 'trade-2',
      amount: 1705,
      timestamp: new Date(now - 600000),
      entryType: 'profit',
      balanceAfter: 100000,
      description: 'DAI/USDC arb execution settled',
      linkedSettlement: 'exec-2',
    },
    {
      id: 'led-3',
      tradeId: 'repay-1',
      amount: -50000,
      timestamp: new Date(now - 400000),
      entryType: 'loan_repayment',
      balanceAfter: 98295,
      description: 'Flashloan repayment for trade-1',
      linkedSettlement: 'exec-1',
    },
  ];

  const totalRealizedPnL = realizedPnLList.reduce((sum, pnl) => sum + pnl.actualProfit, 0);
  const totalUnrealizedPnL = openPositions.reduce((sum, pos) => sum + pos.unrealizedPnL, 0);

  return {
    overallStatus: Math.random() > 0.7 ? 'healthy' : Math.random() > 0.3 ? 'at_risk' : 'critical',
    totalRealizedPnL,
    totalUnrealizedPnL,
    portfolioBalance: 102380 + totalUnrealizedPnL,
    accountingBalance: 102295,
    realizedPnLList,
    openPositions,
    repaymentStatuses,
    ledgerEntries,
    lastUpdated: new Date(),
  };
};

export const useDashboardStore = create<DashboardStore>((set, get) => ({
  metrics: generateMockMetrics(),
  activities: generateMockActivities(),
  opportunities: generateMockOpportunities(),
  riskCenter: generateMockRiskCenter(),
  executionCenter: generateMockExecutionCenter(),
  marketDataCenter: generateMockMarketDataCenter(),
  settlementCenter: generateMockSettlementCenter(),
  computeCenter: generateMockComputeCenter(),
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

  // Execution center actions
  runSimulation: async (_executionId: string) => {
    set((state) => ({
      executionCenter: {
        ...state.executionCenter,
        currentState: 'awaiting_simulation',
        simulation: { ...state.executionCenter.simulation, status: 'pending' },
      },
    }));
    
    await new Promise((resolve) => setTimeout(resolve, 1500));
    
    const success = Math.random() > 0.3;
    set((state) => ({
      executionCenter: {
        ...state.executionCenter,
        currentState: success ? 'simulated' : 'awaiting_simulation',
        simulation: {
          ...state.executionCenter.simulation,
          status: success ? 'success' : 'failed',
          pass: success,
          executedAt: new Date(),
          errorMessage: success ? undefined : 'Simulation failed: insufficient output',
        },
      },
    }));

    get().addActivity({
      id: `sim-${Date.now()}`,
      type: 'execution',
      timestamp: new Date(),
      title: success ? 'Simulation passed' : 'Simulation failed',
      description: success ? 'Trade simulation completed successfully' : 'Trade simulation revealed issues',
      status: success ? 'healthy' : 'critical',
    });
  },

  broadcastTrade: async (_executionId: string) => {
    set((state) => ({
      executionCenter: {
        ...state.executionCenter,
        currentState: 'queued_broadcast',
        broadcastState: { ...state.executionCenter.broadcastState, status: 'submitted' },
      },
    }));

    await new Promise((resolve) => setTimeout(resolve, 2000));

    const txHash = `0x${Math.random().toString(16).substring(2).padEnd(64, '0')}`;
    set((state) => ({
      executionCenter: {
        ...state.executionCenter,
        currentState: 'broadcasting',
        broadcastState: {
          ...state.executionCenter.broadcastState,
          status: 'pending',
          transactionHash: txHash,
          submittedAt: new Date(),
        },
      },
    }));

    await new Promise((resolve) => setTimeout(resolve, 3000));

    const success = Math.random() > 0.2;
    const blockNumber = Math.floor(Math.random() * 20000000) + 19000000;
    set((state) => ({
      executionCenter: {
        ...state.executionCenter,
        currentState: success ? 'confirmed' : 'failed',
        broadcastState: {
          ...state.executionCenter.broadcastState,
          status: 'mined',
          minedAt: new Date(),
          blockNumber,
          confirmations: success ? Math.floor(Math.random() * 50) + 1 : 0,
        },
        onChainOutcome: {
          ...state.executionCenter.onChainOutcome,
          status: success ? 'success' : 'reverted',
          blockNumber,
          transactionIndex: Math.floor(Math.random() * 100),
          gasUsedActual: Math.floor(Math.random() * 500000) + 100000,
          actualOutput: success ? Math.random() * 100000 : undefined,
          errorReason: success ? undefined : 'Reverted: insufficient output',
          settledAt: new Date(),
        },
      },
    }));

    get().addActivity({
      id: `broadcast-${Date.now()}`,
      type: 'execution',
      timestamp: new Date(),
      title: success ? 'Trade executed successfully' : 'Trade execution failed',
      description: success ? `Confirmed on-chain at block ${blockNumber}` : 'Transaction reverted on-chain',
      status: success ? 'healthy' : 'critical',
    });
  },

  retryExecution: async (_executionId: string) => {
    set((state) => ({
      executionCenter: {
        ...state.executionCenter,
        currentState: 'awaiting_simulation',
        simulation: { ...state.executionCenter.simulation, status: 'pending' },
        onChainOutcome: { ...state.executionCenter.onChainOutcome, status: 'pending' },
      },
    }));

    await new Promise((resolve) => setTimeout(resolve, 1000));
    
    get().addActivity({
      id: `retry-${Date.now()}`,
      type: 'execution',
      timestamp: new Date(),
      title: 'Execution retry initiated',
      description: 'Failed execution queued for re-simulation and retry',
      status: 'warning',
    });
  },

  updateBroadcastState: (_executionId: string, state: BroadcastState) =>
    set((s) => ({
      executionCenter: {
        ...s.executionCenter,
        broadcastState: state,
      },
    })),

  updateOnChainOutcome: (_executionId: string, outcome: OnChainOutcome) =>
    set((s) => ({
      executionCenter: {
        ...s.executionCenter,
        onChainOutcome: outcome,
      },
    })),

  getExecution: (_executionId: string) => get().executionCenter,

  // Settlement center actions
  closePosition: (positionId: string) => {
    set((state) => ({
      settlementCenter: {
        ...state.settlementCenter,
        openPositions: state.settlementCenter.openPositions.map((pos) =>
          pos.id === positionId ? { ...pos, status: 'liquidating' as const } : pos
        ),
      },
    }));

    get().addActivity({
      id: `close-${Date.now()}`,
      type: 'settlement',
      timestamp: new Date(),
      title: 'Position liquidation initiated',
      description: `Position ${positionId} marked for closing`,
      status: 'warning',
    });
  },

  recordRepayment: (repaymentId: string, amount: number) => {
    set((state) => ({
      settlementCenter: {
        ...state.settlementCenter,
        repaymentStatuses: state.settlementCenter.repaymentStatuses.map((rep) =>
          rep.id === repaymentId
            ? {
                ...rep,
                repaidAmount: rep.repaidAmount + amount,
                status:
                  rep.repaidAmount + amount >= rep.amount
                    ? ('completed' as const)
                    : ('partially_repaid' as const),
              }
            : rep
        ),
      },
    }));

    get().addActivity({
      id: `repay-${Date.now()}`,
      type: 'settlement',
      timestamp: new Date(),
      title: 'Repayment recorded',
      description: `$${amount.toLocaleString()} recorded for obligation ${repaymentId}`,
      status: 'healthy',
    });
  },

  generateLedgerExport: (_timeRange: { start: Date; end: Date }) => {
    get().addActivity({
      id: `export-${Date.now()}`,
      type: 'settlement',
      timestamp: new Date(),
      title: 'Ledger export generated',
      description: 'Portfolio report generated and ready for download',
      status: 'healthy',
    });
  },

  compareExpectedVsRealized: (tradeId: string) => {
    get().addActivity({
      id: `compare-${Date.now()}`,
      type: 'settlement',
      timestamp: new Date(),
      title: 'Performance analysis',
      description: `Expected vs realized comparison for ${tradeId}`,
      status: 'healthy',
    });
  },

  refreshFeeds: () => {
    set({ marketDataCenter: generateMockMarketDataCenter() });
    get().addActivity({
      id: `market-refresh-${Date.now()}`,
      type: 'market_feed',
      timestamp: new Date(),
      title: 'Market feeds refreshed',
      description: 'Oracle feeds refreshed for Pyth, Chainlink, and fallback sources',
      status: 'healthy',
    });
  },

  getFeedByName: (name: 'Pyth' | 'Chainlink' | 'Fallback') => get().marketDataCenter.feeds.find((feed) => feed.name === name),

  // Compute and TEE center actions
  verifyPayload: async (requestId: string) => {
    set((state) => ({
      computeCenter: {
        ...state.computeCenter,
        validations: state.computeCenter.validations.map((v) =>
          v.requestId === requestId ? { ...v, status: 'passed' as const } : v
        ),
      },
    }));

    get().addActivity({
      id: `verify-${Date.now()}`,
      type: 'execution',
      timestamp: new Date(),
      title: 'Payload verification completed',
      description: `Request ${requestId} payload verified and passed validation`,
      status: 'healthy',
    });
  },

  replayInference: async (requestId: string) => {
    set((state) => ({
      computeCenter: {
        ...state.computeCenter,
        inferenceRequests: state.computeCenter.inferenceRequests.map((req) =>
          req.id === requestId ? { ...req, status: 'processing' as const } : req
        ),
      },
    }));

    await new Promise((resolve) => setTimeout(resolve, 1500));

    set((state) => ({
      computeCenter: {
        ...state.computeCenter,
        inferenceRequests: state.computeCenter.inferenceRequests.map((req) =>
          req.id === requestId ? { ...req, status: 'completed' as const, processingTimeMs: Math.floor(Math.random() * 2000) + 500 } : req
        ),
      },
    }));

    get().addActivity({
      id: `replay-${Date.now()}`,
      type: 'execution',
      timestamp: new Date(),
      title: 'Inference replay completed',
      description: `Request ${requestId} reprocessed and completed successfully`,
      status: 'healthy',
    });
  },

  viewTrace: (requestId: string) => {
    const trace = get().computeCenter.traces.find((t) => t.requestId === requestId);
    if (trace) {
      get().addActivity({
        id: `trace-view-${Date.now()}`,
        type: 'execution',
        timestamp: new Date(),
        title: 'Trace record accessed',
        description: `Trace ${trace.traceId} for request ${requestId} opened for inspection`,
        status: 'healthy',
      });
    }
  },

  inspectSignature: (requestId: string) => {
    const signature = get().computeCenter.signatures.find((s) => s.requestId === requestId);
    if (signature) {
      get().addActivity({
        id: `sig-inspect-${Date.now()}`,
        type: 'execution',
        timestamp: new Date(),
        title: 'Signature details inspected',
        description: `Signature verification for request ${requestId} opened: ${signature.signatureStatus}`,
        status: signature.signatureStatus === 'verified' ? 'healthy' : 'warning',
      });
    }
  },
}));
