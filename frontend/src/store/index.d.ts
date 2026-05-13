import { SystemMetrics, ActivityEvent, Opportunity, RiskCenter, ExecutionCenter, BroadcastState, OnChainOutcome, SettlementCenter, MarketDataCenter, OracleFeedStatus, ComputeCenter } from '@/types';
interface DashboardStore {
    metrics: SystemMetrics;
    activities: ActivityEvent[];
    loading: boolean;
    lastRefresh: Date | null;
    opportunities: Opportunity[];
    riskCenter: RiskCenter;
    executionCenter: ExecutionCenter;
    marketDataCenter: MarketDataCenter;
    simulateOpportunity: (id: string) => Promise<'valid' | 'marginal' | 'invalid'>;
    approveOpportunity: (id: string) => void;
    rejectOpportunity: (id: string, reason: string) => void;
    getOpportunity: (id: string) => Opportunity | undefined;
    setMetrics: (metrics: SystemMetrics) => void;
    setActivities: (activities: ActivityEvent[]) => void;
    setLoading: (loading: boolean) => void;
    addActivity: (activity: ActivityEvent) => void;
    refreshData: () => Promise<void>;
    acknowledgeBreaker: (breakerId: string) => void;
    acknowledgeOverride: (overrideId: string) => void;
    triggerEmergencyStop: (reason: string, by: string) => void;
    clearEmergencyStop: () => void;
    runSimulation: (executionId: string) => Promise<void>;
    broadcastTrade: (executionId: string) => Promise<void>;
    retryExecution: (executionId: string) => Promise<void>;
    updateBroadcastState: (executionId: string, state: BroadcastState) => void;
    updateOnChainOutcome: (executionId: string, outcome: OnChainOutcome) => void;
    getExecution: (executionId: string) => ExecutionCenter;
    settlementCenter: SettlementCenter;
    closePosition: (positionId: string) => void;
    recordRepayment: (repaymentId: string, amount: number) => void;
    generateLedgerExport: (timeRange: {
        start: Date;
        end: Date;
    }) => void;
    compareExpectedVsRealized: (tradeId: string) => void;
    refreshFeeds: () => void;
    getFeedByName: (name: 'Pyth' | 'Chainlink' | 'Fallback') => OracleFeedStatus | undefined;
    computeCenter: ComputeCenter;
    verifyPayload: (requestId: string) => Promise<void>;
    replayInference: (requestId: string) => Promise<void>;
    viewTrace: (requestId: string) => void;
    inspectSignature: (requestId: string) => void;
}
export declare const useDashboardStore: import("zustand").UseBoundStore<import("zustand").StoreApi<DashboardStore>>;
export {};
//# sourceMappingURL=index.d.ts.map