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
//# sourceMappingURL=index.d.ts.map