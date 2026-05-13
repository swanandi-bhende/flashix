import { SystemMetrics, ActivityEvent, Opportunity } from '@/types';
interface DashboardStore {
    metrics: SystemMetrics;
    activities: ActivityEvent[];
    loading: boolean;
    lastRefresh: Date | null;
    opportunities: Opportunity[];
    simulateOpportunity: (id: string) => Promise<'valid' | 'marginal' | 'invalid'>;
    approveOpportunity: (id: string) => void;
    rejectOpportunity: (id: string, reason: string) => void;
    getOpportunity: (id: string) => Opportunity | undefined;
    setMetrics: (metrics: SystemMetrics) => void;
    setActivities: (activities: ActivityEvent[]) => void;
    setLoading: (loading: boolean) => void;
    addActivity: (activity: ActivityEvent) => void;
    refreshData: () => Promise<void>;
}
export declare const useDashboardStore: import("zustand").UseBoundStore<import("zustand").StoreApi<DashboardStore>>;
export {};
//# sourceMappingURL=index.d.ts.map