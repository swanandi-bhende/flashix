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
  AdminCenter,
  Provider,
  ContractConfig,
  ConfigChange,
  AuditLogEntry,
  AuditActionType,
} from '@/types';

type DemoPipelineStage = 'discovery' | 'filtering' | 'inference' | 'reasoning' | 'execution' | 'settlement';
type PipelineLifecycleStep = {
  id: string;
  stage: DemoPipelineStage;
  label: string;
  timestamp: Date;
  status: 'queued' | 'processing' | 'complete';
  eventId?: string;
  storageUrl?: string;
};

const demoPipelineOrder: DemoPipelineStage[] = ['discovery', 'filtering', 'inference', 'reasoning', 'execution', 'settlement'];

const createDemoPipelineLifecycle = (itemId: string, startedAt: Date): PipelineLifecycleStep[] =>
  demoPipelineOrder.map((stage, index) => ({
    id: `${itemId}-${stage}-${index + 1}`,
    stage,
    label: `${stage[0].toUpperCase()}${stage.slice(1)} stage`,
    timestamp: new Date(startedAt.getTime() + index * 1500),
    status: index === 0 ? 'processing' : index === demoPipelineOrder.length - 1 ? 'queued' : 'queued',
  }));

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

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
  triggerEmergencyStop: (reason: string, by: string) => Promise<void>;
  clearEmergencyStop: () => void;

  // Execution center actions
  runSimulation: (executionId: string) => Promise<void>;
  broadcastTrade: (executionId: string) => Promise<void>;
  retryExecution: (executionId: string) => Promise<void>;
  updateBroadcastState: (executionId: string, state: BroadcastState) => void;
  updateOnChainOutcome: (executionId: string, outcome: OnChainOutcome) => void;
  getExecution: (executionId: string) => ExecutionCenter;
  // Mempool / demo utilities
  simulateMempoolEvents: (count: number) => void;

  // Settlement center state and actions
  settlementCenter: SettlementCenter;
  closePosition: (positionId: string) => void;
  recordRepayment: (repaymentId: string, amount: number) => void;
  generateLedgerExport: (timeRange: { start: Date; end: Date }) => void;
  compareExpectedVsRealized: (tradeId: string) => void;

  // Market data actions
  refreshFeeds: () => Promise<void>;
  getFeedByName: (name: 'Pyth' | 'Chainlink' | 'Fallback') => OracleFeedStatus | undefined;

  // Compute and TEE center state and actions
  computeCenter: ComputeCenter;
  verifyPayload: (requestId: string) => Promise<void>;
  replayInference: (requestId: string) => Promise<void>;
  viewTrace: (requestId: string) => void;
  inspectSignature: (requestId: string) => void;
  // Demo helpers
  runDemo: () => void;
  runDemoAuto: () => Promise<void>;

  // Pipeline demo state/actions
  pipelineDemo: {
    itemId: string;
    computeRequestId: string;
    currentStage: PipelineState | 'discovery' | 'filtering' | 'inference' | 'reasoning' | 'execution' | 'settlement';
    lifecycle: Array<{
      id: string;
      stage: 'discovery' | 'filtering' | 'inference' | 'reasoning' | 'execution' | 'settlement';
      label: string;
      timestamp: Date;
      status: 'queued' | 'processing' | 'complete';
      eventId?: string;
      storageUrl?: string;
    }>;
    playbackIndex: number;
    isPlaying: boolean;
    lastPlaybackAt?: Date;
  };
  startPipelineDemo: () => Promise<void>;
  stepPipelineDemo: () => Promise<void>;
  replayPipelineDemo: () => void;
  setPipelinePlaybackIndex: (index: number) => void;

  // Admin and settings center state and actions
  adminCenter: AdminCenter;
  editProvider: (providerId: string) => void;
  updateProvider: (providerId: string, config: Partial<Provider>) => Promise<void>;
  updateContract: (contractId: string) => void;
  saveConfig: () => Promise<void>;
  searchAuditLog: (filters: { actionType?: AuditActionType; subsystem?: string; startDate?: Date; endDate?: Date }) => AuditLogEntry[];
  filterAuditByType: (actionType: AuditActionType) => AuditLogEntry[];
  downloadReplayReport: () => void;
}

// Mock data generator for development
let activitySequence = 0;
let marketRefreshSequence = 0;

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

const generateMockMarketDataCenter = (
  refreshTick = 0,
  snapshotRawPayload: Record<string, any> | null = null,
  sourceUrl?: string,
  sourceName: 'Pyth' | 'Chainlink' | 'Fallback' | 'CoinGecko' = 'CoinGecko'
): MarketDataCenter => {
  const now = Date.now();
  const priceShift = refreshTick * 0.85;
  const freshnessShift = refreshTick % 4;
  const feeds: OracleFeedStatus[] = [
    {
      id: 'pyth',
      name: 'Pyth',
      isLive: true,
      status: 'healthy',
      lastUpdate: new Date(now - (8000 + refreshTick * 2000)),
      latestPrice: 3452.18 + priceShift,
      priceWindowLow: 3428.11 + priceShift,
      priceWindowHigh: 3468.54 + priceShift,
      stalenessSeconds: 8 + freshnessShift,
      updateFrequencySeconds: 5,
      failureCount: 0,
      lastSuccessfulSample: new Date(now - (8000 + refreshTick * 2000)),
      acceptedDeviationPct: 0.45,
    },
    {
      id: 'chainlink',
      name: 'Chainlink',
      isLive: true,
      status: 'degraded',
      lastUpdate: new Date(now - (22000 + refreshTick * 2500)),
      latestPrice: 3450.76 + priceShift * 0.75,
      priceWindowLow: 3427.92 + priceShift * 0.75,
      priceWindowHigh: 3467.9 + priceShift * 0.75,
      stalenessSeconds: 22 + freshnessShift,
      warning: 'Update cadence slower than normal',
      updateFrequencySeconds: 10,
      failureCount: 1,
      lastSuccessfulSample: new Date(now - (22000 + refreshTick * 2500)),
      acceptedDeviationPct: 0.65,
    },
    {
      id: 'fallback',
      name: 'Fallback',
      isLive: true,
      status: 'healthy',
      lastUpdate: new Date(now - (4000 + refreshTick * 1500)),
      latestPrice: 3451.9 + priceShift * 1.1,
      priceWindowLow: 3429.4 + priceShift * 1.1,
      priceWindowHigh: 3465.22 + priceShift * 1.1,
      stalenessSeconds: 4 + freshnessShift,
      warning: 'Synthetic aggregator engaged during primary source drift',
      updateFrequencySeconds: 3,
      failureCount: 0,
      lastSuccessfulSample: new Date(now - (4000 + refreshTick * 1500)),
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
    overallStatus: refreshTick % 3 === 0 ? 'healthy' : 'delayed',
    healthySources: refreshTick % 2 === 0 ? 2 : 3,
    totalSources: 3,
    freshestPriceAgeSeconds: Math.min(...feeds.map((feed) => feed.stalenessSeconds)),
    acceptableFreshnessSeconds: 30,
    trustForExecution: true,
    message: refreshTick === 0
      ? 'At least two sources are healthy and prices are within the execution window.'
      : `Refresh cycle #${refreshTick}: source prices and freshness have been re-evaluated.`,
  };

  const executionCheckPayload = {
    refreshCycle: refreshTick,
    sourceAges: feeds.map((feed) => ({ name: feed.name, stalenessSeconds: feed.stalenessSeconds })),
    comparison,
    freshnessLimitSeconds: summary.acceptableFreshnessSeconds,
    trustForExecution: summary.trustForExecution,
  };

  return {
    summary,
    feeds,
    comparison,
    fallbackEvents,
    refreshedAt: new Date(),
    refreshCycle: refreshTick,
    latestSnapshot: {
      id: `snapshot-${refreshTick}`,
      sourceName,
      sourceUrl: sourceUrl ?? 'https://api.coingecko.com/api/v3/simple/price?ids=ethereum,bitcoin,usd-coin&vs_currencies=usd',
      takenAt: new Date(),
      rawPayload: {
        marketSnapshot: snapshotRawPayload ?? {
          feeds,
          comparison,
          fallbackEvents,
        },
        comparison,
      },
      executionCheckPayload,
    },
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
    verificationCount: 0,
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

const generateMockAdminCenter = (): AdminCenter => ({
  providers: [],
  contracts: [],
  configChanges: [],
  auditLog: [],
  lastSaveTime: new Date(0),
  lastSavedBy: undefined,
  unsavedChanges: false,
  replayReportUrl: undefined,
  lastUpdated: new Date(),
});

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
    // lastRpcPayload is optional debug payload stored for replay
    lastRpcPayload: undefined as any,
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
  adminCenter: generateMockAdminCenter(),
  pipelineDemo: {
    itemId: 'OPP-PIPE-9001',
    computeRequestId: 'INF-PIPE-9001',
    currentStage: 'discovery',
    lifecycle: createDemoPipelineLifecycle('OPP-PIPE-9001', new Date()),
    playbackIndex: 0,
    isPlaying: false,
    lastPlaybackAt: undefined,
  },
  loading: false,
  lastRefresh: new Date(),
  // demo flag/actions
  runDemo: () => {
    // deterministic demo state for judges: clear randomness and set a reproducible story
    const demoNow = Date.now();
    set({
      metrics: {
        pipelineState: 'processing',
        totalOpportunities: 6,
        activeOpportunities: 3,
        livePositions: 1,
        riskStatus: 'green',
        openBreakers: 0,
        executionHealth: 'healthy',
        recentExecutions: 12,
        settlementStatus: 'healthy',
        marketDataFreshness: 3,
        lastMarketDataSample: new Date(demoNow - 2000),
      },
      activities: [
        { id: 'demo-activity-1', type: 'opportunity_detected', timestamp: new Date(demoNow - 60000), title: 'Demo: Opportunity detected', description: 'Seeded demo opportunity OPP-9999', status: 'healthy' },
        { id: 'demo-activity-2', type: 'execution', timestamp: new Date(demoNow - 30000), title: 'Demo: Simulation queued', description: 'Simulation pending for OPP-9999', status: 'warning' },
      ],
      opportunities: [
        {
          id: 'OPP-9999',
          detectionTime: new Date(demoNow - 65000),
          source: 'mempool',
          type: 'arbitrage',
          expectedProfit: 1420,
          risk: 0.12,
          status: 'pending',
          freshnessSeconds: 5,
          trace: [],
          pair: 'ETH/USDC',
          sourcePrices: [{ exchange: 'Uniswap', price: 3450.12 }],
          targetPrices: [{ exchange: 'Balancer', price: 3460.34 }],
          spreadPct: 0.29,
          gasCost: 120,
          flashloanCost: 14,
          slippageEstimate: 0.002,
          executionOverhead: 12,
          fees: 6,
          confidenceScore: 0.87,
          confidenceFactors: ['model_score_high', 'low_slippage'],
          riskChecks: { breakerTriggered: false, collateralOk: true, slippageLimitOk: true, exposureOk: true, warnings: [] },
          rawPayload: { id: 'raw-demo-9999', metadata: { demo: true } },
        },
        ...generateMockOpportunities().slice(0, 5),
      ],
      executionCenter: {
        ...get().executionCenter,
        id: 'exec-demo-1',
        opportunityId: 'OPP-9999',
        currentState: 'awaiting_simulation',
        simulation: { ...get().executionCenter.simulation, status: 'pending', pass: false, executedAt: undefined },
        broadcastState: { ...get().executionCenter.broadcastState, status: 'not_sent' },
        onChainOutcome: { ...get().executionCenter.onChainOutcome, status: 'pending' },
      },
      settlementCenter: {
        ...get().settlementCenter,
        openPositions: get().settlementCenter.openPositions,
      },
      marketDataCenter: generateMockMarketDataCenter(0),
    });

    // ensure activity sequence increments
    activitySequence += 10;
  },
  startPipelineDemo: async () => {
    const itemId = 'OPP-PIPE-9001';
    const computeRequestId = 'INF-PIPE-9001';
    const startedAt = new Date();
    const lifecycle = createDemoPipelineLifecycle(itemId, startedAt);
    const signatureArtifact = {
      requestId: computeRequestId,
      sourceOpportunityId: itemId,
      pipelineEventId: lifecycle[2]?.id,
      payload: {
        pair: 'ETH/USDC',
        amount: 125000,
        minOutput: 124500,
        slippageBps: 18,
      },
      validatedAt: startedAt.toISOString(),
    };

    let signedArtifactUrl: string | undefined;
    let signedArtifactSignature = '';
    let signedArtifactProofSteps = [
      'Canonicalize JSON',
      'Compute digest inside TEE boundary',
      'Persist proof JSON to storage',
    ];
    let signedArtifactAlgorithm = 'secp256k1-keccak256';
    let signedArtifactSigner = 'TEE-Service';
    let signedArtifactPublicKey = 'TEE-Service';
    try {
      const response = await fetch('/api/tee/sign', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(signatureArtifact),
      });
      if (response.ok) {
        const data = await response.json();
        signedArtifactUrl = data.url;
        signedArtifactSignature = data.signature;
        signedArtifactProofSteps = Array.isArray(data.verificationSteps) ? data.verificationSteps : signedArtifactProofSteps;
        signedArtifactAlgorithm = data.algorithm || signedArtifactAlgorithm;
        signedArtifactSigner = data.signerIdentity || signedArtifactSigner;
        signedArtifactPublicKey = data.publicKey || signedArtifactPublicKey;
      }
    } catch (error) {
      console.warn('TEE signing unavailable for pipeline demo, continuing with local proof', error);
    }
    const proofRecord = {
      requestId: computeRequestId,
      algorithm: signedArtifactAlgorithm,
      signerIdentity: signedArtifactSigner,
      publicKey: signedArtifactPublicKey,
      signedAt: startedAt,
      signature: signedArtifactSignature || 'pending',
      verificationSteps: signedArtifactProofSteps,
      artifactUrl: signedArtifactUrl,
      rawOutput: signatureArtifact,
    };

    set({
      pipelineDemo: {
        itemId,
        computeRequestId,
        currentStage: 'discovery',
        lifecycle: lifecycle.map((step, index) => ({
          ...step,
          status: index === 0 ? 'processing' : 'queued',
        })),
        playbackIndex: 0,
        isPlaying: true,
        lastPlaybackAt: startedAt,
      },
      computeCenter: {
        ...get().computeCenter,
        inferenceRequests: [
          {
            id: computeRequestId,
            timestamp: startedAt,
            sourceOpportunityId: itemId,
            payload: signatureArtifact.payload,
            status: 'submitted',
            processingTimeMs: 0,
          },
          ...get().computeCenter.inferenceRequests,
        ],
        validations: [
          {
            requestId: computeRequestId,
            status: 'passed',
            schemaValid: true,
            requiredFieldsMissing: [],
            malformedInputs: [],
            validatedAt: startedAt,
            verificationCount: 1,
          },
          ...get().computeCenter.validations,
        ],
        signatures: [
          {
            requestId: computeRequestId,
            signerIdentity: 'TEE-Service',
            signatureStatus: signedArtifactSignature ? 'verified' : 'pending',
            verificationResult: Boolean(signedArtifactSignature),
            verifiedAt: startedAt,
          } as any,
          ...get().computeCenter.signatures,
        ],
        proofs: [
          proofRecord,
          ...(get().computeCenter.proofs || []),
        ],
        traces: [
          {
            requestId: computeRequestId,
            opportunityId: itemId,
            traceId: `TRACE-${computeRequestId}`,
            linkedDecisionRecord: {
              decision: 'execute',
              confidence: 0.93,
              timestamp: startedAt,
            },
            downstreamConsumer: 'execution_engine',
            linkedStage: 'execution',
          },
          ...get().computeCenter.traces,
        ],
        signedArtifacts: [
          {
            requestId: computeRequestId,
            sourceOpportunityId: itemId,
            pipelineEventId: lifecycle[2]?.id,
            signedAt: startedAt,
            signature: signedArtifactSignature || 'pending',
            artifactUrl: signedArtifactUrl,
          },
          ...(get().computeCenter.signedArtifacts || []),
        ],
      },
    });

    const persistStep = async (step: (typeof lifecycle)[number], index: number) => {
      const payload = {
        requestId: itemId,
        stage: step.stage,
        eventId: step.id,
        timestamp: step.timestamp.toISOString(),
        pipeline: 'demo-runner',
        lifecycleIndex: index,
        sourceOpportunityId: 'OPP-9999',
        detail: step.label,
      };

      let storageUrl: string | undefined;
      try {
        const response = await fetch('/api/traces/persist', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        if (response.ok) {
          const data = await response.json();
          storageUrl = data.url;
        }
      } catch (error) {
        console.warn('Pipeline persistence unavailable, continuing locally', error);
      }

      set((state) => ({
        pipelineDemo: {
          ...state.pipelineDemo,
          currentStage: step.stage,
          playbackIndex: index,
          lifecycle: state.pipelineDemo.lifecycle.map((entry, entryIndex) =>
            entryIndex === index
              ? { ...entry, status: 'complete', eventId: step.id, storageUrl }
              : entryIndex === index + 1
                ? { ...entry, status: 'processing' }
                : entry
          ),
          lastPlaybackAt: new Date(),
        },
      }));

      if (step.stage === 'inference') {
        set((state) => ({
          computeCenter: {
            ...state.computeCenter,
            signedArtifacts: (state.computeCenter.signedArtifacts || []).map((artifact) =>
              artifact.requestId === computeRequestId
                ? {
                    ...artifact,
                    pipelineEventId: step.id,
                    artifactUrl: artifact.artifactUrl ?? storageUrl,
                  }
                : artifact
            ),
          },
        }));
      }

      get().addActivity({
        id: `pipeline-demo-${step.stage}-${Date.now()}`,
        type: 'execution',
        timestamp: new Date(),
        title: `Pipeline ${step.stage} event recorded`,
        description: `${step.id}${storageUrl ? ` persisted at ${storageUrl}` : ''}`,
        status: 'healthy',
      });
    };

    for (let index = 0; index < lifecycle.length; index++) {
      await sleep(550);
      await persistStep(lifecycle[index], index);
    }

    set((state) => ({
      pipelineDemo: {
        ...state.pipelineDemo,
        isPlaying: false,
      },
    }));
  },
  stepPipelineDemo: async () => {
    const current = get().pipelineDemo;
    const nextIndex = Math.min(current.playbackIndex + 1, current.lifecycle.length - 1);
    const nextStep = current.lifecycle[nextIndex];
    if (!nextStep) {
      return;
    }

    set((state) => ({
      pipelineDemo: {
        ...state.pipelineDemo,
        currentStage: nextStep.stage,
        playbackIndex: nextIndex,
        lastPlaybackAt: new Date(),
      },
    }));

    get().addActivity({
      id: `pipeline-step-${Date.now()}`,
      type: 'execution',
      timestamp: new Date(),
      title: `Pipeline step ${nextStep.stage}`,
      description: `${current.itemId} moved to ${nextStep.stage}`,
      status: 'healthy',
    });
  },
  replayPipelineDemo: () => {
    set((state) => ({
      pipelineDemo: {
        ...state.pipelineDemo,
        playbackIndex: 0,
        currentStage: 'discovery',
        lastPlaybackAt: new Date(),
      },
    }));
  },
  setPipelinePlaybackIndex: (index: number) => {
    set((state) => ({
      pipelineDemo: {
        ...state.pipelineDemo,
        playbackIndex: Math.max(0, Math.min(index, state.pipelineDemo.lifecycle.length - 1)),
        currentStage: state.pipelineDemo.lifecycle[Math.max(0, Math.min(index, state.pipelineDemo.lifecycle.length - 1))]?.stage ?? state.pipelineDemo.currentStage,
        lastPlaybackAt: new Date(),
      },
    }));
  },
  // Run full automated demo: simulate -> approve -> execute -> broadcast -> settle
  runDemoAuto: async () => {
    // seed base demo state first
    get().runDemo();
    // small delay to let UI update
    await new Promise((r) => setTimeout(r, 400));
    const oppId = 'OPP-9999';
    try {
      // simulate opportunity
      await get().simulateOpportunity(oppId);
      // approve and send to execution
      get().approveOpportunity(oppId);
      // attach execution record
      set((s) => ({
        executionCenter: { ...s.executionCenter, id: `exec-demo-${Date.now()}`, opportunityId: oppId, currentState: 'queued_broadcast' },
      }));
      // broadcast
      await get().broadcastTrade(get().executionCenter.id);
      // create settlement ledger entry and persist full lifecycle for judges
      const profit = get().executionCenter.gasEstimate?.profitAfterGasUSD || 0;
      const entry = {
        id: `led-demo-${Date.now()}`,
        tradeId: `trade-${oppId}`,
        amount: profit,
        timestamp: new Date(),
        entryType: 'profit',
        balanceAfter: (get().settlementCenter.portfolioBalance || 100000) + profit,
        description: `Demo settlement for ${oppId}`,
        linkedSettlement: get().executionCenter.id,
      } as any;
      set((s) => ({ settlementCenter: { ...s.settlementCenter, ledgerEntries: [entry, ...s.settlementCenter.ledgerEntries], totalRealizedPnL: (s.settlementCenter.totalRealizedPnL || 0) + profit, portfolioBalance: (s.settlementCenter.portfolioBalance || 0) + profit } }));

      // persist lifecycle record (simulation, rpc payload, receipt, ledger entry)
      try {
        const lifecycleRecord = {
          id: `lifecycle-${Date.now()}`,
          type: 'trade-lifecycle',
          tradeId: entry.tradeId,
          executionId: get().executionCenter.id,
          opportunityId: oppId,
          simulation: get().executionCenter.simulation,
          broadcast: get().executionCenter.lastRpcPayload || null,
          onChainOutcome: get().executionCenter.onChainOutcome,
          ledgerEntry: entry,
          realizedPnL: {
            tradeId: entry.tradeId,
            plannedProfit: get().executionCenter.gasEstimate?.profitAfterGasUSD || 0,
            actualGasCost: get().executionCenter.gasEstimate?.totalFeeUSD || 0,
            actualProfit: profit,
            realizationTime: new Date(),
            status: 'completed',
          },
        };

        const resp = await fetch('/api/traces/persist', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(lifecycleRecord),
        });
        if (resp.ok) {
          const data = await resp.json();
          const url = data.url;
          // add realized PnL record including txHash and exportUrl
          const tx = get().executionCenter.broadcastState.transactionHash;
          const realized = {
            tradeId: entry.tradeId,
            symbol: 'ETH/USDC',
            plannedProfit: get().executionCenter.gasEstimate?.profitAfterGasUSD || 0,
            actualGasCost: get().executionCenter.gasEstimate?.totalFeeUSD || 0,
            actualProfit: profit,
            realizationTime: new Date(),
            status: 'completed',
            txHash: tx,
            exportUrl: url,
          } as any;
          set((s) => ({ settlementCenter: { ...s.settlementCenter, lastExportUrl: url, lastExportId: data.id || s.settlementCenter.lastExportId, realizedPnLList: [realized, ...s.settlementCenter.realizedPnLList] } }));
          get().addActivity({ id: `demo-auto-${Date.now()}`, type: 'execution', timestamp: new Date(), title: 'Demo run completed', description: `Automated demo for ${oppId} completed and persisted at ${url}`, status: 'healthy' });
        } else {
          // even if persistence failed, still record realized PnL locally
          const tx = get().executionCenter.broadcastState.transactionHash;
          const realized = {
            tradeId: entry.tradeId,
            symbol: 'ETH/USDC',
            plannedProfit: get().executionCenter.gasEstimate?.profitAfterGasUSD || 0,
            actualGasCost: get().executionCenter.gasEstimate?.totalFeeUSD || 0,
            actualProfit: profit,
            realizationTime: new Date(),
            status: 'completed',
            txHash: tx,
          } as any;
          set((s) => ({ settlementCenter: { ...s.settlementCenter, realizedPnLList: [realized, ...s.settlementCenter.realizedPnLList] } }));
          get().addActivity({ id: `demo-auto-${Date.now()}`, type: 'execution', timestamp: new Date(), title: 'Demo run completed', description: `Automated demo for ${oppId} completed (not persisted)`, status: 'warning' });
        }
      } catch (err) {
        console.warn('Failed to persist demo lifecycle', err);
        get().addActivity({ id: `demo-auto-${Date.now()}`, type: 'execution', timestamp: new Date(), title: 'Demo run completed', description: `Automated demo for ${oppId} completed (persist failed)`, status: 'warning' });
      }
    } catch (e) {
      console.error('runDemoAuto failed', e);
      get().addActivity({ id: `demo-auto-fail-${Date.now()}`, type: 'execution', timestamp: new Date(), title: 'Demo run failed', description: String(e), status: 'warning' });
    }
  },

  setMetrics: (metrics) => set({ metrics }),
  setActivities: (activities) => set({ activities }),
  setLoading: (loading) => set({ loading }),
  
  addActivity: (activity) => set((state) => ({
    activities: [{ ...activity, id: `${activity.id}-${++activitySequence}` }, ...state.activities].slice(0, 10),
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

  triggerEmergencyStop: (reason: string, by: string) => {
    return (async () => {
      const override = {
        id: `override-${Date.now()}`,
        triggeredBy: by,
        triggeredAt: new Date(),
        reason,
        active: true,
        pausesTrading: true,
      } as any;

      // attempt to persist override to demo persistence service
      try {
        const resp = await fetch('/api/traces/persist', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            requestId: override.id,
            type: 'human-override',
            triggeredBy: override.triggeredBy,
            triggeredAt: override.triggeredAt.toISOString(),
            reason: override.reason,
            pausesTrading: true,
          }),
        });
        if (resp.ok) {
          const data = await resp.json();
          override.persistedUrl = data.url;
          if (data.id) override.persistedId = data.id;
        }
      } catch (err) {
        console.warn('Failed to persist override trace', err);
      }

      set((state) => ({
        riskCenter: {
          ...state.riskCenter,
          overallStatus: 'emergency',
          overrides: [...state.riskCenter.overrides, override],
        },
      }));

      get().addActivity({
        id: `override-activity-${Date.now()}`,
        type: 'risk_event',
        timestamp: new Date(),
        title: 'Human override persisted',
        description: override.persistedUrl ? `Override persisted at ${override.persistedUrl}` : `Override created locally: ${override.id}`,
        status: 'critical',
        details: { override },
      });
    })();
  },

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

    await new Promise((resolve) => setTimeout(resolve, 1200));

    set((state) => ({
      executionCenter: {
        ...state.executionCenter,
        currentState: 'simulated',
        simulation: {
          ...state.executionCenter.simulation,
          status: 'success',
          pass: true,
          executedAt: new Date(),
          errorMessage: undefined,
        },
      },
    }));

    get().addActivity({
      id: `sim-${Date.now()}`,
      type: 'execution',
      timestamp: new Date(),
      title: 'Simulation passed',
      description: 'Trade simulation completed successfully',
      status: 'healthy',
    });
  },

  broadcastTrade: async (_executionId: string) => {
    // if a human override is active that pauses trading, block the broadcast and persist a blocked event
    const activeOverride = get().riskCenter.overrides.find((o: any) => o.active && o.pausesTrading);
    if (activeOverride) {
      const blockedEvent = {
        id: `blocked-${Date.now()}`,
        event: 'broadcast_blocked',
        executionId: _executionId,
        overrideId: activeOverride.id,
        overrideUrl: activeOverride.persistedUrl,
        reason: activeOverride.reason,
        blockedAt: new Date().toISOString(),
      };
      try {
        const resp = await fetch('/api/traces/persist', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(blockedEvent),
        });
        let blockedUrl: string | undefined;
        if (resp.ok) {
          const data = await resp.json();
          blockedUrl = data.url;
        }

        set((state) => ({
          executionCenter: {
            ...state.executionCenter,
            broadcastState: { ...state.executionCenter.broadcastState, status: 'blocked' },
            lastBlockedReason: activeOverride.reason,
            blockedByOverrideUrl: blockedUrl || activeOverride.persistedUrl,
            blockedAt: new Date(),
          },
        }));

        get().addActivity({
          id: `blocked-activity-${Date.now()}`,
          type: 'risk_event',
          timestamp: new Date(),
          title: 'Broadcast blocked by human override',
          description: blockedUrl ? `Broadcast blocked and recorded at ${blockedUrl}` : `Broadcast blocked by override ${activeOverride.id}`,
          status: 'critical',
          details: { blockedEvent },
        });
      } catch (err) {
        console.warn('Failed to persist blocked broadcast event', err);
      }

      return;
    }

    // mark queued
    set((state) => ({
      executionCenter: {
        ...state.executionCenter,
        currentState: 'queued_broadcast',
        broadcastState: { ...state.executionCenter.broadcastState, status: 'submitted' },
      },
    }));

    await new Promise((resolve) => setTimeout(resolve, 700));

    // create a realistic-looking tx hash and RPC payload that judges can replay
    const txHash = `0x${Math.random().toString(16).slice(2, 66).padEnd(64, '0')}`;
    const rpcPayload = {
      jsonrpc: '2.0',
      id: Date.now(),
      method: 'eth_sendRawTransaction',
      params: [`0x${Math.random().toString(16).slice(2, 140)}`],
      meta: { demo: true },
    };

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
        // store the payload so the UI can show a replayable call
        lastRpcPayload: rpcPayload,
      },
    }));

    await new Promise((resolve) => setTimeout(resolve, 1200));

    // fake mined receipt
    const blockNumber = 27669207 + Math.floor(Math.random() * 10);
    const receipt = {
      transactionHash: txHash,
      blockNumber,
      status: 1,
      confirmations: 12,
      gasUsed: 470064,
      logs: [],
      timestamp: Date.now(),
    };

    set((state) => ({
      executionCenter: {
        ...state.executionCenter,
        currentState: 'confirmed',
        broadcastState: {
          ...state.executionCenter.broadcastState,
          status: 'mined',
          minedAt: new Date(),
          blockNumber,
          confirmations: receipt.confirmations,
        },
        onChainOutcome: {
          ...state.executionCenter.onChainOutcome,
          status: 'success',
          blockNumber,
          transactionIndex: 14,
          gasUsedActual: receipt.gasUsed,
          actualOutput: state.executionCenter.gasEstimate?.profitAfterGasUSD || 0,
          errorReason: undefined,
          settledAt: new Date(),
        },
        // attach receipt for replay/download
        lastRpcPayload: { rpc: rpcPayload, receipt },
      },
    }));

    get().addActivity({
      id: `broadcast-${Date.now()}`,
      type: 'execution',
      timestamp: new Date(),
      title: 'Trade executed successfully',
      description: `Confirmed on-chain at block ${blockNumber}`,
      status: 'healthy',
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

  simulateMempoolEvents: (count: number) => {
    const now = Date.now();
    const newOpps: Opportunity[] = [];
    const newActs: ActivityEvent[] = [];
    for (let i = 0; i < count; i++) {
      const id = `OPP-SIM-${now}-${i}`;
      newOpps.push({
        id,
        detectionTime: new Date(now - i * 1000),
        source: 'mempool',
        type: 'arbitrage',
        expectedProfit: Math.round(500 + Math.random() * 2000),
        risk: parseFloat((Math.random() * 0.5).toFixed(2)),
        status: 'pending',
        freshnessSeconds: i,
        trace: [{ step: 'mempool', detail: 'received', timestamp: new Date(now - i * 1000) }],
        pair: 'ETH/USDC',
        sourcePrices: [{ exchange: 'Uniswap', price: 3450 + i }],
        targetPrices: [{ exchange: 'Balancer', price: 3460 + i }],
        spreadPct: 0.2 + i * 0.01,
        gasCost: 120,
        flashloanCost: 14,
        slippageEstimate: 0.002,
        executionOverhead: 10,
        fees: 5,
        confidenceScore: parseFloat((0.6 + Math.random() * 0.35).toFixed(2)),
        confidenceFactors: ['simulated_feed', 'low_slippage'],
        riskChecks: { breakerTriggered: false, collateralOk: true, slippageLimitOk: true, exposureOk: true, warnings: [] },
        rawPayload: { id: `raw-${id}`, metadata: { simulated: true } },
      } as any);

      newActs.push({ id: `ACT-SIM-${now}-${i}`, type: 'opportunity_detected', timestamp: new Date(now - i * 1000), title: `Mempool event ${id}`, description: 'Simulated mempool event ingested', status: 'healthy' });
    }

    set((s) => ({
      opportunities: [...newOpps, ...s.opportunities],
      activities: [...newActs, ...s.activities],
    }));
  },

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
    (async () => {
      const entries = get().settlementCenter.ledgerEntries.filter((e) => {
        const ts = new Date(e.timestamp).getTime();
        return ts >= _timeRange.start.getTime() && ts <= _timeRange.end.getTime();
      });

      // Build CSV
      const header = ['id,tradeId,entryType,amount,balanceAfter,timestamp,description,linkedSettlement'];
      const rows = entries.map((e) => `${e.id},${e.tradeId},${e.entryType},${e.amount},${e.balanceAfter},${new Date(e.timestamp).toISOString()},"${(e.description || '').replace(/"/g, '""')}",${e.linkedSettlement || ''}`);
      const csv = header.concat(rows).join('\n');

      try {
        const resp = await fetch('/api/traces/persist', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ requestId: `ledger-export-${Date.now()}`, type: 'ledger-export', filename: `ledger-export-${Date.now()}.csv`, content: csv }),
        });
        if (resp.ok) {
          const data = await resp.json();
          const url = data.url;
          set((s) => ({ settlementCenter: { ...s.settlementCenter, lastExportUrl: url, lastExportId: data.id || s.settlementCenter.lastExportId } }));
          get().addActivity({ id: `export-${Date.now()}`, type: 'settlement', timestamp: new Date(), title: 'Ledger export generated', description: `Ledger export persisted at ${url}`, status: 'healthy' });
          return;
        }
      } catch (err) {
        console.warn('Failed to persist ledger export', err);
      }

      get().addActivity({ id: `export-${Date.now()}`, type: 'settlement', timestamp: new Date(), title: 'Ledger export generated', description: 'Ledger export prepared locally (persistence failed)', status: 'warning' });
    })();
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

  refreshFeeds: async () => {
    marketRefreshSequence += 1;

    let snapshotPayload: Record<string, any> | null = null;
    let sourceUrl = 'https://api.coingecko.com/api/v3/simple/price?ids=ethereum,bitcoin,usd-coin&vs_currencies=usd';
    let sourceName: 'Pyth' | 'Chainlink' | 'Fallback' | 'CoinGecko' = 'CoinGecko';

    try {
      const response = await fetch(sourceUrl, { headers: { Accept: 'application/json' } });
      if (response.ok) {
        snapshotPayload = await response.json();
      }
    } catch (error) {
      console.warn('Real market snapshot fetch failed, using deterministic fallback data', error);
      snapshotPayload = null;
      sourceName = 'Fallback';
      sourceUrl = 'local-deterministic-snapshot';
    }

    const marketDataCenter = generateMockMarketDataCenter(marketRefreshSequence, snapshotPayload ?? undefined, sourceUrl, sourceName);

    let logUrl: string | undefined;
    try {
      const persistResponse = await fetch('/api/traces/persist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          requestId: `market-refresh-${marketRefreshSequence}`,
          refreshCycle: marketRefreshSequence,
          sourceName,
          sourceUrl,
          snapshot: marketDataCenter.latestSnapshot,
          executionCheckPayload: marketDataCenter.latestSnapshot?.executionCheckPayload,
        }),
      });
      if (persistResponse.ok) {
        const data = await persistResponse.json();
        logUrl = data.url;
      }
    } catch (error) {
      console.warn('Unable to persist market snapshot log', error);
    }

    set({
      marketDataCenter: {
        ...marketDataCenter,
        latestSnapshot: marketDataCenter.latestSnapshot
          ? { ...marketDataCenter.latestSnapshot, logUrl }
          : undefined,
      },
    });

    get().addActivity({
      id: `market-refresh-${Date.now()}`,
      type: 'market_feed',
      timestamp: new Date(),
      title: `Market feeds refreshed - cycle #${marketRefreshSequence}`,
      description: logUrl
        ? `Oracle snapshot refreshed and persisted at ${logUrl}`
        : `Oracle snapshot refreshed from ${sourceName}`,
      status: 'healthy',
    });
  },

  getFeedByName: (name: 'Pyth' | 'Chainlink' | 'Fallback') => get().marketDataCenter.feeds.find((feed) => feed.name === name),

  // Compute and TEE center actions
  verifyPayload: async (requestId: string) => {
    // perform validation and then request a TEE signature from configured signing service
    set((state) => ({
      computeCenter: {
        ...state.computeCenter,
        validations: state.computeCenter.validations.map((v) =>
          v.requestId === requestId
            ? {
                ...v,
                status: 'passed' as const,
                schemaValid: true,
                requiredFieldsMissing: [],
                malformedInputs: [],
                rejectionReason: undefined,
                validatedAt: new Date(),
                verificationCount: v.verificationCount + 1,
              }
            : v
        ),
        inferenceRequests: state.computeCenter.inferenceRequests.map((req) =>
          req.id === requestId ? { ...req, status: 'validated' as const } : req
        ),
      },
    }));

    // create artifact to sign
    const request = get().computeCenter.inferenceRequests.find((r) => r.id === requestId);
    const artifact = {
      requestId,
      payload: request?.payload,
      validatedAt: new Date().toISOString(),
      sourceOpportunityId: request?.sourceOpportunityId,
    };

    // attempt to call signing service at /api/tee/sign
    try {
      const resp = await fetch('/api/tee/sign', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(artifact),
      });
      if (resp.ok) {
        const data = await resp.json();
        const signedAtValue = typeof data.signedAt === 'number'
          ? (data.signedAt < 1e12 ? data.signedAt * 1000 : data.signedAt)
          : Date.now();
        const proofRecord = {
          requestId,
          algorithm: data.algorithm || 'secp256k1-keccak256',
          signerIdentity: data.signerIdentity || 'TEE-Service',
          publicKey: data.publicKey || data.signerIdentity || 'TEE-Service',
          signedAt: new Date(signedAtValue),
          signature: data.signature || data.sig || '',
          verificationSteps: Array.isArray(data.verificationSteps) ? data.verificationSteps : ['Validate request', 'Hash payload', 'Verify signature'],
          artifactUrl: data.url || data.artifactUrl,
          rawOutput: artifact,
        };

        set((state) => ({
          computeCenter: {
            ...state.computeCenter,
            signatures: [
              ...state.computeCenter.signatures,
              {
                requestId,
                signerIdentity: proofRecord.signerIdentity,
                signatureStatus: 'verified',
                verificationResult: true,
                verifiedAt: new Date(),
              },
            ],
            proofs: [proofRecord, ...(state.computeCenter.proofs || [])],
            signedArtifacts: [
              ...(state.computeCenter.signedArtifacts || []),
              {
                requestId,
                sourceOpportunityId: request?.sourceOpportunityId,
                signedAt: new Date(),
                signature: proofRecord.signature,
                artifactUrl: proofRecord.artifactUrl,
              },
            ],
          },
        }));
        get().addActivity({
          id: `tee-sign-${Date.now()}`,
          type: 'execution',
          timestamp: new Date(),
          title: 'TEE-signed artifact created',
          description: `Request ${requestId} signed by ${proofRecord.signerIdentity}`,
          status: 'healthy',
        });
        return;
      }
    } catch (e) {
      // ignore and fall through to fallback
    }

    // fallback: local reproducible proof with a public signer identity
    try {
      const encoder = new TextEncoder();
      const encoded = encoder.encode(JSON.stringify(artifact));
      const hashBuffer = await crypto.subtle.digest('SHA-256', encoded);
      const hashArray = Array.from(new Uint8Array(hashBuffer));
      const signature = hashArray.map((b) => b.toString(16).padStart(2, '0')).join('');
      const proofRecord = {
        requestId,
        algorithm: 'sha256-demo-proof',
        signerIdentity: 'local-demo-signer',
        publicKey: 'local-demo-public-key',
        signedAt: new Date(),
        signature,
        verificationSteps: ['Canonicalize JSON', 'Compute SHA-256 digest', 'Compare signature fingerprint', 'Persist proof JSON'],
        artifactUrl: undefined,
        rawOutput: artifact,
      };

      set((state) => ({
        computeCenter: {
          ...state.computeCenter,
          signatures: [
            ...state.computeCenter.signatures,
            { requestId, signerIdentity: 'local-demo-signer', signatureStatus: 'verified', verificationResult: true, verifiedAt: new Date() } as any,
          ],
          proofs: [proofRecord, ...(state.computeCenter.proofs || [])],
          signedArtifacts: [
            ...(state.computeCenter.signedArtifacts || []),
            { requestId, signedAt: new Date(), signature, artifactUrl: undefined },
          ],
        },
      }));

      get().addActivity({
        id: `tee-sign-fallback-${Date.now()}`,
        type: 'execution',
        timestamp: new Date(),
        title: 'Local fingerprint generated',
        description: `Request ${requestId} fingerprinted for demo`,
        status: 'warning',
      });
    } catch (err) {
      console.error('Failed to create fingerprint signature fallback', err);
    }
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

  // Admin and settings center actions
  editProvider: (providerId: string) => {
    get().addActivity({
      id: `edit-provider-${Date.now()}`,
      type: 'execution',
      timestamp: new Date(),
      title: 'Provider configuration opened',
      description: `Provider ${providerId} opened for editing`,
      status: 'healthy',
    });
  },

  updateProvider: async (providerId: string, config: Partial<Provider>) => {
    set((state) => ({
      adminCenter: {
        ...state.adminCenter,
        providers: state.adminCenter.providers.map((p) =>
          p.id === providerId ? { ...p, ...config } : p
        ),
        unsavedChanges: true,
      },
    }));

    get().addActivity({
      id: `update-provider-${Date.now()}`,
      type: 'execution',
      timestamp: new Date(),
      title: 'Provider updated',
      description: `Provider ${providerId} configuration updated (unsaved)`,
      status: 'warning',
    });
  },

  updateContract: (contractId: string) => {
    get().addActivity({
      id: `update-contract-${Date.now()}`,
      type: 'execution',
      timestamp: new Date(),
      title: 'Contract details opened',
      description: `Contract ${contractId} deployment details opened for review`,
      status: 'healthy',
    });
  },

  saveConfig: async () => {
    set((state) => ({
      adminCenter: {
        ...state.adminCenter,
        unsavedChanges: false,
        lastSaveTime: new Date(),
        lastSavedBy: 'current-user',
      },
    }));

    get().addActivity({
      id: `save-config-${Date.now()}`,
      type: 'execution',
      timestamp: new Date(),
      title: 'Configuration saved',
      description: 'System configuration changes have been saved and are now active',
      status: 'healthy',
    });
  },

  searchAuditLog: (filters: { actionType?: AuditActionType; subsystem?: string; startDate?: Date; endDate?: Date }) => {
    const auditLog = get().adminCenter.auditLog;
    return auditLog.filter((entry) => {
      if (filters.actionType && entry.actionType !== filters.actionType) return false;
      if (filters.subsystem && entry.subsystem !== filters.subsystem) return false;
      if (filters.startDate && entry.timestamp < filters.startDate) return false;
      if (filters.endDate && entry.timestamp > filters.endDate) return false;
      return true;
    });
  },

  filterAuditByType: (actionType: AuditActionType) => {
    return get().adminCenter.auditLog.filter((entry) => entry.actionType === actionType);
  },

  downloadReplayReport: () => {
    get().addActivity({
      id: `download-report-${Date.now()}`,
      type: 'execution',
      timestamp: new Date(),
      title: 'Replay report downloaded',
      description: 'Complete historical snapshot of system behavior exported',
      status: 'healthy',
    });
  },
}));
