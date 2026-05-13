export type HealthStatus = 'healthy' | 'warning' | 'critical';
export type PipelineState = 'idle' | 'processing' | 'degraded' | 'halted';
export type RiskStatus = 'green' | 'elevated' | 'blocked';
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
    marketDataFreshness: number;
    lastMarketDataSample: Date;
}
export type ActivityEventType = 'opportunity_detected' | 'risk_event' | 'execution' | 'settlement' | 'market_feed';
export interface ActivityEvent {
    id: string;
    type: ActivityEventType;
    timestamp: Date;
    title: string;
    description: string;
    status: HealthStatus;
    details?: Record<string, any>;
}
export interface PipelineStatus {
    state: PipelineState;
    activeWorkers: number;
    totalWorkers: number;
    processedToday: number;
    failedToday: number;
    avgLatency: number;
}
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
    trace?: Array<{
        step: string;
        detail: string;
        timestamp: Date;
    }>;
    pair?: string;
    sourcePrices?: Array<{
        exchange: string;
        price: number;
    }>;
    targetPrices?: Array<{
        exchange: string;
        price: number;
    }>;
    spreadPct?: number;
    gasCost?: number;
    flashloanCost?: number;
    slippageEstimate?: number;
    executionOverhead?: number;
    fees?: number;
    confidenceScore?: number;
    confidenceFactors?: string[];
    riskChecks?: {
        breakerTriggered?: boolean;
        collateralOk?: boolean;
        slippageLimitOk?: boolean;
        exposureOk?: boolean;
        warnings?: string[];
    };
    rawPayload?: Record<string, any>;
}
export interface RiskEvent {
    id: string;
    timestamp: Date;
    severity: 'low' | 'medium' | 'high' | 'critical';
    category: string;
    description: string;
    breaker?: string;
}
export interface ExecutionRecord {
    id: string;
    opportunityId: string;
    timestamp: Date;
    status: 'pending' | 'confirmed' | 'failed';
    gasCost: number;
    profit: number;
    txHash?: string;
}
export interface SettlementStatus {
    pendingRepayments: number;
    completedToday: number;
    failedToday: number;
    lastSettlementTime: Date;
    ledgerBalance: number;
}
export interface MarketDataFeed {
    name: string;
    lastUpdate: Date;
    isHealthy: boolean;
    samples: number;
}
export interface CircuitBreaker {
    id: string;
    name: string;
    trigger: string;
    threshold: number;
    current: number;
    status: 'healthy' | 'warning' | 'triggered';
    activatedAt?: Date;
    affectedTradeCount?: number;
}
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
export interface OpenPosition {
    id: string;
    tradeName: string;
    exposureSize: number;
    entryTime: Date;
    currentState: 'active' | 'at_risk' | 'critical';
    affectsBreakerIds?: string[];
    affectsLimits?: string[];
}
export interface HumanOverride {
    id: string;
    triggeredBy: string;
    triggeredAt: Date;
    reason: string;
    active: boolean;
    pausesTrading: boolean;
}
export interface RiskCenter {
    overallStatus: 'green' | 'elevated' | 'blocked' | 'emergency';
    breakers: CircuitBreaker[];
    limits: PortfolioLimits;
    positions: OpenPosition[];
    overrides: HumanOverride[];
    lastUpdated: Date;
}
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
export interface GasEstimate {
    gasUsageUnits: number;
    gasPriceWei: number;
    totalFeeUSD: number;
    totalFeeETH: number;
    profitAfterGasUSD: number;
    profitMarginPct: number;
    remainsProfitable: boolean;
}
export interface BroadcastState {
    status: 'not_sent' | 'submitted' | 'pending' | 'mined';
    transactionHash?: string;
    submittedAt?: Date;
    minedAt?: Date;
    blockNumber?: number;
    confirmations?: number;
}
export interface OnChainOutcome {
    status: 'success' | 'reverted' | 'partial_fail' | 'unexpected' | 'pending';
    blockNumber?: number;
    transactionIndex?: number;
    gasUsedActual?: number;
    actualOutput?: number;
    errorReason?: string;
    settledAt?: Date;
}
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
//# sourceMappingURL=index.d.ts.map