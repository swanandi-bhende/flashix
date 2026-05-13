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
const generateMockRiskCenter = () => {
    const now = Date.now();
    return {
        overallStatus: Math.random() > 0.7 ? 'green' : Math.random() > 0.4 ? 'elevated' : 'blocked',
        breakers: [
            {
                id: 'breaker-1',
                name: 'Daily Loss',
                trigger: 'Cumulative loss exceeds $50k',
                threshold: 50000,
                current: Math.floor(Math.random() * 60000),
                status: Math.random() > 0.8 ? 'triggered' : Math.random() > 0.4 ? 'warning' : 'healthy',
                activatedAt: Math.random() > 0.7 ? new Date(now - Math.floor(Math.random() * 3600000)) : undefined,
                affectedTradeCount: Math.floor(Math.random() * 10),
            },
            {
                id: 'breaker-2',
                name: 'Slippage',
                trigger: 'Single trade slippage > 1%',
                threshold: 1,
                current: parseFloat((Math.random() * 1.5).toFixed(2)),
                status: Math.random() > 0.85 ? 'warning' : 'healthy',
                affectedTradeCount: Math.floor(Math.random() * 5),
            },
            {
                id: 'breaker-3',
                name: 'Exposure',
                trigger: 'Concurrent position > $5M',
                threshold: 5000000,
                current: Math.floor(Math.random() * 6000000),
                status: 'healthy',
            },
        ],
        limits: {
            dailyLossLimit: 50000,
            currentDailyLoss: Math.floor(Math.random() * 60000),
            collateralRatio: 2.5,
            collateralLimit: 2.0,
            maxConcurrentPositions: 20,
            currentPositions: Math.floor(Math.random() * 22),
            slippageLimitPct: 1,
            currentSlippagePct: parseFloat((Math.random() * 0.8).toFixed(2)),
        },
        positions: [
            { id: 'pos-1', tradeName: 'ETH/USDC Arb', exposureSize: 250000, entryTime: new Date(now - 3600000), currentState: 'active', affectsBreakerIds: ['breaker-1'], affectsLimits: [] },
            { id: 'pos-2', tradeName: 'DAI/USDC Arb', exposureSize: 180000, entryTime: new Date(now - 7200000), currentState: 'active', affectsLimits: [] },
            { id: 'pos-3', tradeName: 'WBTC/BTC Arb', exposureSize: 420000, entryTime: new Date(now - 1800000), currentState: 'at_risk', affectsBreakerIds: ['breaker-3'] },
        ],
        overrides: [
            { id: 'override-1', triggeredBy: 'admin@flashix.com', triggeredAt: new Date(now - 7200000), reason: 'Manual override for maintenance', active: false, pausesTrading: true },
        ],
        lastUpdated: new Date(),
    };
};
const generateMockExecutionCenter = () => {
    const now = Date.now();
    const states = [
        'awaiting_simulation',
        'simulated',
        'queued_broadcast',
        'broadcasting',
        'confirmed',
        'failed',
    ];
    const currentState = states[Math.floor(Math.random() * states.length)];
    const txHash = `0x${Math.random().toString(16).substring(2).padEnd(64, '0')}`;
    return {
        id: `exec-${Math.random().toString(36).substring(2, 9)}`,
        opportunityId: `opp-${Math.random().toString(36).substring(2, 9)}`,
        currentState,
        simulation: {
            id: `sim-${Math.random().toString(36).substring(2, 9)}`,
            status: ['pending', 'success', 'failed'][Math.floor(Math.random() * 3)],
            pass: Math.random() > 0.2,
            expectedOutput: `${(Math.random() * 100).toFixed(4)} USDC`,
            expectedAmount: Math.random() * 100000,
            warnings: Math.random() > 0.6 ? ['High slippage detected', 'Low liquidity pool'] : [],
            gasEstimatedUnits: Math.floor(Math.random() * 500000) + 100000,
            executedAt: new Date(now - Math.floor(Math.random() * 300000)),
        },
        gasEstimate: {
            gasUsageUnits: Math.floor(Math.random() * 500000) + 100000,
            gasPriceWei: Math.floor(Math.random() * 100) + 20,
            totalFeeUSD: parseFloat((Math.random() * 500 + 50).toFixed(2)),
            totalFeeETH: parseFloat((Math.random() * 0.5 + 0.05).toFixed(4)),
            profitAfterGasUSD: parseFloat((Math.random() * 5000 + 500).toFixed(2)),
            profitMarginPct: parseFloat((Math.random() * 10 + 1).toFixed(2)),
            remainsProfitable: Math.random() > 0.2,
        },
        broadcastState: {
            status: currentState === 'awaiting_simulation' ? 'not_sent' : currentState === 'queued_broadcast' ? 'submitted' : currentState === 'broadcasting' ? 'pending' : 'mined',
            transactionHash: ['confirmed', 'partial_success'].includes(currentState) ? txHash : undefined,
            submittedAt: ['broadcasting', 'confirmed', 'partial_success'].includes(currentState) ? new Date(now - Math.floor(Math.random() * 300000)) : undefined,
            minedAt: ['confirmed', 'partial_success'].includes(currentState) ? new Date(now - Math.floor(Math.random() * 60000)) : undefined,
            blockNumber: ['confirmed', 'partial_success'].includes(currentState) ? Math.floor(Math.random() * 20000000) + 19000000 : undefined,
            confirmations: ['confirmed', 'partial_success'].includes(currentState) ? Math.floor(Math.random() * 50) + 1 : undefined,
        },
        onChainOutcome: {
            status: currentState === 'confirmed' ? 'success' : currentState === 'failed' ? 'reverted' : 'pending',
            blockNumber: ['confirmed', 'partial_success'].includes(currentState) ? Math.floor(Math.random() * 20000000) + 19000000 : undefined,
            transactionIndex: ['confirmed', 'partial_success'].includes(currentState) ? Math.floor(Math.random() * 100) : undefined,
            gasUsedActual: ['confirmed', 'partial_success'].includes(currentState) ? Math.floor(Math.random() * 500000) + 100000 : undefined,
            actualOutput: ['confirmed', 'partial_success'].includes(currentState) ? Math.random() * 100000 : undefined,
            errorReason: currentState === 'failed' ? 'Insufficient output amount' : undefined,
            settledAt: ['confirmed', 'partial_success'].includes(currentState) ? new Date(now - Math.floor(Math.random() * 60000)) : undefined,
        },
        lastUpdated: new Date(),
    };
};
export const useDashboardStore = create((set, get) => ({
    metrics: generateMockMetrics(),
    activities: generateMockActivities(),
    opportunities: generateMockOpportunities(),
    riskCenter: generateMockRiskCenter(),
    executionCenter: generateMockExecutionCenter(),
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
    // Risk center actions
    acknowledgeBreaker: (breakerId) => set((state) => ({
        riskCenter: {
            ...state.riskCenter,
            breakers: state.riskCenter.breakers.map((b) => (b.id === breakerId ? { ...b, status: 'healthy' } : b)),
        },
    })),
    acknowledgeOverride: (overrideId) => set((state) => ({
        riskCenter: {
            ...state.riskCenter,
            overrides: state.riskCenter.overrides.map((o) => (o.id === overrideId ? { ...o, active: false } : o)),
        },
    })),
    triggerEmergencyStop: (reason, by) => set((state) => ({
        riskCenter: {
            ...state.riskCenter,
            overallStatus: 'emergency',
            overrides: [...state.riskCenter.overrides, {
                    id: `override-${Date.now()}`,
                    triggeredBy: by,
                    triggeredAt: new Date(),
                    reason,
                    active: true,
                    pausesTrading: true,
                }],
        },
    })),
    clearEmergencyStop: () => set((state) => ({
        riskCenter: {
            ...state.riskCenter,
            overrides: state.riskCenter.overrides.map((o) => ({ ...o, active: false })),
        },
    })),
    // Execution center actions
    runSimulation: async (_executionId) => {
        set((state) => ({
            executionCenter: {
                ...state.executionCenter,
                currentState: 'awaiting_simulation',
                simulation: { ...state.executionCenter.simulation, status: 'pending' },
            },
        }));
        await new Promise((resolve) => setTimeout(resolve, 1500));
        const success = Math.random() > 0.3;
        set((state) => ({
            executionCenter: {
                ...state.executionCenter,
                currentState: success ? 'simulated' : 'awaiting_simulation',
                simulation: {
                    ...state.executionCenter.simulation,
                    status: success ? 'success' : 'failed',
                    pass: success,
                    executedAt: new Date(),
                    errorMessage: success ? undefined : 'Simulation failed: insufficient output',
                },
            },
        }));
        get().addActivity({
            id: `sim-${Date.now()}`,
            type: 'execution',
            timestamp: new Date(),
            title: success ? 'Simulation passed' : 'Simulation failed',
            description: success ? 'Trade simulation completed successfully' : 'Trade simulation revealed issues',
            status: success ? 'healthy' : 'critical',
        });
    },
    broadcastTrade: async (_executionId) => {
        set((state) => ({
            executionCenter: {
                ...state.executionCenter,
                currentState: 'queued_broadcast',
                broadcastState: { ...state.executionCenter.broadcastState, status: 'submitted' },
            },
        }));
        await new Promise((resolve) => setTimeout(resolve, 2000));
        const txHash = `0x${Math.random().toString(16).substring(2).padEnd(64, '0')}`;
        set((state) => ({
            executionCenter: {
                ...state.executionCenter,
                currentState: 'broadcasting',
                broadcastState: {
                    ...state.executionCenter.broadcastState,
                    status: 'pending',
                    transactionHash: txHash,
                    submittedAt: new Date(),
                },
            },
        }));
        await new Promise((resolve) => setTimeout(resolve, 3000));
        const success = Math.random() > 0.2;
        const blockNumber = Math.floor(Math.random() * 20000000) + 19000000;
        set((state) => ({
            executionCenter: {
                ...state.executionCenter,
                currentState: success ? 'confirmed' : 'failed',
                broadcastState: {
                    ...state.executionCenter.broadcastState,
                    status: 'mined',
                    minedAt: new Date(),
                    blockNumber,
                    confirmations: success ? Math.floor(Math.random() * 50) + 1 : 0,
                },
                onChainOutcome: {
                    ...state.executionCenter.onChainOutcome,
                    status: success ? 'success' : 'reverted',
                    blockNumber,
                    transactionIndex: Math.floor(Math.random() * 100),
                    gasUsedActual: Math.floor(Math.random() * 500000) + 100000,
                    actualOutput: success ? Math.random() * 100000 : undefined,
                    errorReason: success ? undefined : 'Reverted: insufficient output',
                    settledAt: new Date(),
                },
            },
        }));
        get().addActivity({
            id: `broadcast-${Date.now()}`,
            type: 'execution',
            timestamp: new Date(),
            title: success ? 'Trade executed successfully' : 'Trade execution failed',
            description: success ? `Confirmed on-chain at block ${blockNumber}` : 'Transaction reverted on-chain',
            status: success ? 'healthy' : 'critical',
        });
    },
    retryExecution: async (_executionId) => {
        set((state) => ({
            executionCenter: {
                ...state.executionCenter,
                currentState: 'awaiting_simulation',
                simulation: { ...state.executionCenter.simulation, status: 'pending' },
                onChainOutcome: { ...state.executionCenter.onChainOutcome, status: 'pending' },
            },
        }));
        await new Promise((resolve) => setTimeout(resolve, 1000));
        get().addActivity({
            id: `retry-${Date.now()}`,
            type: 'execution',
            timestamp: new Date(),
            title: 'Execution retry initiated',
            description: 'Failed execution queued for re-simulation and retry',
            status: 'warning',
        });
    },
    updateBroadcastState: (_executionId, state) => set((s) => ({
        executionCenter: {
            ...s.executionCenter,
            broadcastState: state,
        },
    })),
    updateOnChainOutcome: (_executionId, outcome) => set((s) => ({
        executionCenter: {
            ...s.executionCenter,
            onChainOutcome: outcome,
        },
    })),
    getExecution: (_executionId) => get().executionCenter,
}));
//# sourceMappingURL=index.js.map