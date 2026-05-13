import { create } from 'zustand';
// Mock data generator for development
const generateMockMetrics = () => ({
    pipelineState: ['idle', 'processing', 'degraded', 'halted'][Math.floor(Math.random() * 4)],
    totalOpportunities: Math.floor(Math.random() * 500) + 50,
    activeOpportunities: Math.floor(Math.random() * 30) + 5,
    livePositions: Math.floor(Math.random() * 20) + 2,
    riskStatus: ['green', 'elevated', 'blocked'][Math.floor(Math.random() * 3)],
    openBreakers: Math.floor(Math.random() * 5),
    executionHealth: ['healthy', 'warning', 'critical'][Math.floor(Math.random() * 3)],
    recentExecutions: Math.floor(Math.random() * 100) + 10,
    settlementStatus: ['healthy', 'warning', 'critical'][Math.floor(Math.random() * 3)],
    marketDataFreshness: Math.floor(Math.random() * 30),
    lastMarketDataSample: new Date(Date.now() - Math.floor(Math.random() * 60000)),
});
const generateMockActivities = () => {
    const types = [
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
        status: ['healthy', 'warning', 'critical'][i % 3],
    }));
};
const generateMockOpportunities = () => {
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
        };
    });
};
export const useDashboardStore = create((set, get) => ({
    metrics: generateMockMetrics(),
    activities: generateMockActivities(),
    opportunities: generateMockOpportunities(),
    loading: false,
    lastRefresh: new Date(),
    setMetrics: (metrics) => set({ metrics }),
    setActivities: (activities) => set({ activities }),
    setLoading: (loading) => set({ loading }),
    addActivity: (activity) => set((state) => ({
        activities: [activity, ...state.activities].slice(0, 10),
    })),
    // Opportunity actions
    simulateOpportunity: async (id) => {
        // simulate a pre-flight check (mock)
        await new Promise((r) => setTimeout(r, 400));
        const outcome = Math.random();
        const result = outcome > 0.7 ? 'valid' : outcome > 0.4 ? 'marginal' : 'invalid';
        set((state) => ({
            opportunities: state.opportunities.map((o) => (o.id === id ? { ...o, simulatedResult: result } : o)),
        }));
        return result;
    },
    approveOpportunity: (id) => set((state) => ({
        opportunities: state.opportunities.map((o) => (o.id === id ? { ...o, status: 'executing' } : o)),
    })),
    rejectOpportunity: (id, reason) => set((state) => ({
        opportunities: state.opportunities.map((o) => (o.id === id ? { ...o, status: 'rejected', rejectionReason: reason } : o)),
    })),
    getOpportunity: (id) => {
        const s = get();
        return s.opportunities.find((o) => o.id === id);
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
        }
        catch (error) {
            console.error('Failed to refresh dashboard data:', error);
            set({ loading: false });
        }
    },
}));
//# sourceMappingURL=index.js.map