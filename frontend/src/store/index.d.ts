import { SystemMetrics, ActivityEvent, Opportunity, RiskCenter, ExecutionCenter, BroadcastState, OnChainOutcome } from '@/types';
interface DashboardStore {
    metrics: SystemMetrics;
    activities: ActivityEvent[];
    loading: boolean;
    lastRefresh: Date | null;
    opportunities: Opportunity[];
    riskCenter: RiskCenter;
    executionCenter: ExecutionCenter;
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
}
export declare const useDashboardStore: import("zustand").UseBoundStore<import("zustand").StoreApi<DashboardStore>>;
export {};
//# sourceMappingURL=index.d.ts.map