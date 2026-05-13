// System health statuses
export type HealthStatus = 'healthy' | 'warning' | 'critical';

// Pipeline states
export type PipelineState = 'idle' | 'processing' | 'degraded' | 'halted';

// Risk states
export type RiskStatus = 'green' | 'elevated' | 'blocked';

// Core system metrics
export interface SystemMetrics {
  pipelineState: PipelineState;
  totalOpportunities: number;
  activeOpportunities: number;
  livePositions: number;
  riskStatus: RiskStatus;
  openBreakers: number;
  executionHealth: HealthStatus;
  recentExecutions: number;
  settlementStatus: HealthStatus;
  marketDataFreshness: number; // age in seconds
  lastMarketDataSample: Date;
}

// Activity event types
export type ActivityEventType = 
  | 'opportunity_detected' 
  | 'risk_event' 
  | 'execution' 
  | 'settlement' 
  | 'market_feed';

export interface ActivityEvent {
  id: string;
  type: ActivityEventType;
  timestamp: Date;
  title: string;
  description: string;
  status: HealthStatus;
  details?: Record<string, any>;
}

// Pipeline monitoring
export interface PipelineStatus {
  state: PipelineState;
  activeWorkers: number;
  totalWorkers: number;
  processedToday: number;
  failedToday: number;
  avgLatency: number;
}

// Opportunity
export interface Opportunity {
  id: string;
  detectionTime: Date;
  source: string;
  type: string;
  expectedProfit: number;
  risk: number;
  status: 'pending' | 'executing' | 'completed' | 'failed' | 'rejected';
  rejectionReason?: string;
  simulatedResult?: 'valid' | 'marginal' | 'invalid';
  freshnessSeconds?: number;
  trace?: Array<{ step: string; detail: string; timestamp: Date }>;
  // Market / decision metadata
  pair?: string;
  sourcePrices?: Array<{ exchange: string; price: number }>;
  targetPrices?: Array<{ exchange: string; price: number }>;
  spreadPct?: number;

  // Cost breakdown
  gasCost?: number;
  flashloanCost?: number;
  slippageEstimate?: number;
  executionOverhead?: number;
  fees?: number;

  // Confidence and risk
  confidenceScore?: number; // 0-1
  confidenceFactors?: string[];
  riskChecks?: {
    breakerTriggered?: boolean;
    collateralOk?: boolean;
    slippageLimitOk?: boolean;
    exposureOk?: boolean;
    warnings?: string[];
  };

  // Raw payload for auditing
  rawPayload?: Record<string, any>;
}

// Risk event
export interface RiskEvent {
  id: string;
  timestamp: Date;
  severity: 'low' | 'medium' | 'high' | 'critical';
  category: string;
  description: string;
  breaker?: string;
}

// Execution record
export interface ExecutionRecord {
  id: string;
  opportunityId: string;
  timestamp: Date;
  status: 'pending' | 'confirmed' | 'failed';
  gasCost: number;
  profit: number;
  txHash?: string;
}

// Settlement status
export interface SettlementStatus {
  pendingRepayments: number;
  completedToday: number;
  failedToday: number;
  lastSettlementTime: Date;
  ledgerBalance: number;
}

// Market data feed
export interface MarketDataFeed {
  name: string;
  lastUpdate: Date;
  isHealthy: boolean;
  samples: number;
}

// Circuit breakers
export interface CircuitBreaker {
  id: string;
  name: string;
  trigger: string; // e.g., "Daily Loss", "Slippage", "Exposure"
  threshold: number;
  current: number;
  status: 'healthy' | 'warning' | 'triggered';
  activatedAt?: Date;
  affectedTradeCount?: number;
}

// Portfolio limits
export interface PortfolioLimits {
  dailyLossLimit: number;
  currentDailyLoss: number;
  collateralRatio: number;
  collateralLimit: number;
  maxConcurrentPositions: number;
  currentPositions: number;
  slippageLimitPct: number;
  currentSlippagePct: number;
}

// Open position
export interface OpenPosition {
  id: string;
  tradeName: string;
  exposureSize: number;
  entryTime: Date;
  currentState: 'active' | 'at_risk' | 'critical';
  affectsBreakerIds?: string[];
  affectsLimits?: string[];
}

// Human override
export interface HumanOverride {
  id: string;
  triggeredBy: string;
  triggeredAt: Date;
  reason: string;
  active: boolean;
  pausesTrading: boolean;
}

// Risk center state
export interface RiskCenter {
  overallStatus: 'green' | 'elevated' | 'blocked' | 'emergency';
  breakers: CircuitBreaker[];
  limits: PortfolioLimits;
  positions: OpenPosition[];
  overrides: HumanOverride[];
  lastUpdated: Date;
}
