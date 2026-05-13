import { SystemMetrics, ActivityEvent } from '@/types';
interface DashboardStore {
    metrics: SystemMetrics;
    activities: ActivityEvent[];
    loading: boolean;
    lastRefresh: Date | null;
    setMetrics: (metrics: SystemMetrics) => void;
    setActivities: (activities: ActivityEvent[]) => void;
    setLoading: (loading: boolean) => void;
    addActivity: (activity: ActivityEvent) => void;
    refreshData: () => Promise<void>;
}
export declare const useDashboardStore: import("zustand").UseBoundStore<import("zustand").StoreApi<DashboardStore>>;
export {};
//# sourceMappingURL=index.d.ts.map