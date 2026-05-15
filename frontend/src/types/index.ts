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

export interface OracleFeedStatus {
  id: string;
  name: 'Pyth' | 'Chainlink' | 'Fallback';
  isLive: boolean;
  status: 'healthy' | 'delayed' | 'degraded' | 'offline';
  lastUpdate: Date;
  latestPrice: number;
  priceWindowLow: number;
  priceWindowHigh: number;
  stalenessSeconds: number;
  warning?: string;
  updateFrequencySeconds: number;
  failureCount: number;
  lastSuccessfulSample: Date;
  acceptedDeviationPct: number;
}

export interface MarketFallbackEvent {
  id: string;
  primarySource: 'Pyth' | 'Chainlink';
  fallbackSource: 'Fallback';
  triggeredAt: Date;
  resolvedAt?: Date;
  triggerReason: string;
  durationSeconds?: number;
}

export interface MarketComparison {
  pythVsChainlinkPct: number;
  pythVsFallbackPct: number;
  chainlinkVsFallbackPct: number;
  hasMaterialMismatch: boolean;
  trustForExecution: boolean;
}

export interface MarketDataHealthSummary {
  overallStatus: 'healthy' | 'delayed' | 'degraded' | 'critical';
  healthySources: number;
  totalSources: number;
  freshestPriceAgeSeconds: number;
  acceptableFreshnessSeconds: number;
  trustForExecution: boolean;
  message: string;
}

export interface MarketDataCenter {
  summary: MarketDataHealthSummary;
  feeds: OracleFeedStatus[];
  comparison: MarketComparison;
  fallbackEvents: MarketFallbackEvent[];
  refreshedAt: Date;
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

// Execution simulation result
export interface SimulationResult {
  id: string;
  status: 'pending' | 'success' | 'failed';
  pass: boolean;
  expectedOutput: string;
  expectedAmount: number;
  warnings: string[];
  gasEstimatedUnits: number;
  executedAt?: Date;
  errorMessage?: string;
}

// Gas cost estimation
export interface GasEstimate {
  gasUsageUnits: number;
  gasPriceWei: number;
  totalFeeUSD: number;
  totalFeeETH: number;
  profitAfterGasUSD: number;
  profitMarginPct: number;
  remainsProfitable: boolean;
}

// Broadcast state tracking
export interface BroadcastState {
  status: 'not_sent' | 'submitted' | 'pending' | 'mined';
  transactionHash?: string;
  submittedAt?: Date;
  minedAt?: Date;
  blockNumber?: number;
  confirmations?: number;
}

// On-chain outcome
export interface OnChainOutcome {
  status: 'success' | 'reverted' | 'partial_fail' | 'unexpected' | 'pending';
  blockNumber?: number;
  transactionIndex?: number;
  gasUsedActual?: number;
  actualOutput?: number;
  errorReason?: string;
  settledAt?: Date;
}

// Execution center state for single trade
export interface ExecutionCenter {
  id: string;
  opportunityId: string;
  currentState: 'awaiting_simulation' | 'simulated' | 'queued_broadcast' | 'broadcasting' | 'confirmed' | 'failed' | 'partial_success';
  simulation: SimulationResult;
  gasEstimate: GasEstimate;
  broadcastState: BroadcastState;
  onChainOutcome: OnChainOutcome;
  lastUpdated: Date;
}

// Realized PnL tracking
export interface RealizedPnL {
  tradeId: string;
  symbol: string;
  plannedProfit: number;
  actualGasCost: number;
  actualProfit: number;
  realizationTime: Date;
  status: 'completed' | 'partial' | 'failed';
}

// Portfolio position tracking
export interface PortfolioPosition {
  id: string;
  tradeId: string;
  symbol: string;
  size: number;
  entryTime: Date;
  entryPrice: number;
  currentMark: number;
  exposure: number;
  unrealizedPnL: number;
  status: 'active' | 'liquidating' | 'at_risk';
}

// Repayment obligation
export interface RepaymentStatus {
  id: string;
  obligationType: 'flashloan' | 'borrowed_collateral' | 'settlement_fee' | 'other';
  amount: number;
  borrowedAt: Date;
  dueDate?: Date;
  repaidAmount: number;
  status: 'pending' | 'partially_repaid' | 'completed' | 'overdue';
  linkedExecutionId?: string;
}

// Ledger entry for accounting
export interface LedgerEntry {
  id: string;
  tradeId: string;
  amount: number;
  timestamp: Date;
  entryType: 'profit' | 'loss' | 'gas_fee' | 'loan_repayment' | 'withdrawal' | 'deposit' | 'adjustment';
  balanceAfter: number;
  description: string;
  linkedSettlement?: string;
}

// Settlement and portfolio center
export interface SettlementCenter {
  overallStatus: 'healthy' | 'at_risk' | 'critical';
  totalRealizedPnL: number;
  totalUnrealizedPnL: number;
  portfolioBalance: number;
  accountingBalance: number;
  realizedPnLList: RealizedPnL[];
  openPositions: PortfolioPosition[];
  repaymentStatuses: RepaymentStatus[];
  ledgerEntries: LedgerEntry[];
  lastUpdated: Date;
}

// Inference request (TEE input)
export interface InferenceRequest {
  id: string;
  timestamp: Date;
  sourceOpportunityId: string;
  payload: Record<string, any>;
  status: 'submitted' | 'validating' | 'validated' | 'processing' | 'completed' | 'failed';
  processingTimeMs?: number;
}

// Payload validation result
export interface PayloadValidation {
  requestId: string;
  status: 'passed' | 'failed';
  schemaValid: boolean;
  requiredFieldsMissing: string[];
  malformedInputs: string[];
  rejectionReason?: string;
  validatedAt: Date;
  verificationCount: number;
}

// Signature verification check
export interface SignatureCheck {
  requestId: string;
  signerIdentity: string;
  signatureStatus: 'verified' | 'failed' | 'pending';
  verificationResult: boolean;
  mismatchWarning?: string;
  verifiedAt?: Date;
}

// Trace linking (connects inference to reasoning path)
export interface TraceLink {
  requestId: string;
  opportunityId: string;
  traceId: string;
  linkedDecisionRecord: Record<string, any>;
  downstreamConsumer: string;
  linkedStage: string;
}

// Compute and TEE center state
export interface ComputeCenter {
  inferenceRequests: InferenceRequest[];
  validations: PayloadValidation[];
  signatures: SignatureCheck[];
  traces: TraceLink[];
  overallHealth: 'green' | 'elevated' | 'blocked';
  lastUpdated: Date;
}

// Provider configuration (external dependencies)
export interface Provider {
  id: string;
  name: string;
  type: 'market_data' | 'rpc' | 'tee' | 'execution';
  endpoint: string;
  status: 'active' | 'inactive' | 'degraded';
  isHealthy: boolean;
  lastHealthCheck: Date;
  failureCount: number;
  averageLatencyMs: number;
  details: Record<string, any>;
}

// Contract configuration
export interface ContractConfig {
  id: string;
  name: string;
  address: string;
  network: string;
  version: string;
  deploymentTime: Date;
  verificationStatus: 'verified' | 'unverified' | 'pending';
  isActive: boolean;
  lastUpdateTime: Date;
  compilationDetails?: Record<string, any>;
}

// Configuration change tracking
export interface ConfigChange {
  id: string;
  timestamp: Date;
  changedBy: string;
  changeType: 'provider_update' | 'contract_update' | 'setting_change' | 'config_save';
  affectedResource: string;
  previousValue?: Record<string, any>;
  newValue: Record<string, any>;
  status: 'pending' | 'active' | 'reverted';
  description: string;
}

// Audit log entry
export type AuditActionType = 
  | 'config_change' 
  | 'contract_update' 
  | 'operator_action' 
  | 'trade_decision' 
  | 'security_event' 
  | 'system_alert';

export interface AuditLogEntry {
  id: string;
  timestamp: Date;
  actionType: AuditActionType;
  actor: string;
  subsystem: 'admin' | 'pipeline' | 'execution' | 'settlement' | 'risk' | 'market_data' | 'compute';
  description: string;
  details: Record<string, any>;
  severity: 'info' | 'warning' | 'critical';
  linkedResourceId?: string;
}

// Admin and settings control plane
export interface AdminCenter {
  providers: Provider[];
  contracts: ContractConfig[];
  configChanges: ConfigChange[];
  auditLog: AuditLogEntry[];
  lastSaveTime?: Date;
  lastSavedBy?: string;
  unsavedChanges: boolean;
  replayReportUrl?: string;
  lastUpdated: Date;
}
