import { create } from 'zustand';
import { 
  SystemMetrics, 
  ActivityEvent, 
  HealthStatus, 
  PipelineState, 
  RiskStatus 
} from '@/types';

interface DashboardStore {
  metrics: SystemMetrics;
  activities: ActivityEvent[];
  loading: boolean;
  lastRefresh: Date | null;
  
  // Actions
  setMetrics: (metrics: SystemMetrics) => void;
  setActivities: (activities: ActivityEvent[]) => void;
  setLoading: (loading: boolean) => void;
  addActivity: (activity: ActivityEvent) => void;
  refreshData: () => Promise<void>;
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

export const useDashboardStore = create<DashboardStore>((set) => ({
  metrics: generateMockMetrics(),
  activities: generateMockActivities(),
  loading: false,
  lastRefresh: new Date(),

  setMetrics: (metrics) => set({ metrics }),
  setActivities: (activities) => set({ activities }),
  setLoading: (loading) => set({ loading }),
  
  addActivity: (activity) => set((state) => ({
    activities: [activity, ...state.activities].slice(0, 10),
  })),

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
}));
