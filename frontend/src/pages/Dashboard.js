import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Zap, Target, AlertCircle, Cpu, CheckCircle, Database, } from 'lucide-react';
import { Layout, IndicatorCard, ActionButtons, ActivityFeed } from '@/components';
import { useDashboardStore } from '@/store';
export const Dashboard = () => {
    const navigate = useNavigate();
    const { metrics, activities, loading, refreshData, runDemo, runDemoAuto } = useDashboardStore();
    const [showTour, setShowTour] = useState(false);
    const [tourStep, setTourStep] = useState(0);
    useEffect(() => {
        // Auto-refresh every 30 seconds
        const interval = setInterval(() => {
            refreshData();
        }, 30000);
        return () => clearInterval(interval);
    }, [refreshData]);
    const getPipelineStatusDescription = () => {
        const descriptions = {
            idle: 'Workers are idle, waiting for opportunities',
            processing: 'Workers actively processing opportunities',
            degraded: 'System degraded, some workers offline',
            halted: 'Pipeline halted, immediate action required',
        };
        return descriptions[metrics.pipelineState];
    };
    const getRiskStatusDescription = () => {
        const descriptions = {
            green: 'System operating normally, all metrics green',
            elevated: 'Risk elevated, breakers may trigger soon',
            blocked: 'Risk breaker triggered, trading halted',
        };
        return descriptions[metrics.riskStatus];
    };
    const getExecutionHealthDescription = () => {
        const descriptions = {
            healthy: 'All executions completing successfully',
            warning: 'Some execution failures detected',
            critical: 'Critical execution failures, investigate immediately',
        };
        return descriptions[metrics.executionHealth];
    };
    const getSettlementStatusDescription = () => {
        const descriptions = {
            healthy: 'All settlements completing on schedule',
            warning: 'Some settlements delayed, monitoring',
            critical: 'Settlement failures, manual intervention needed',
        };
        return descriptions[metrics.settlementStatus];
    };
    const getPipelineHealthStatus = () => {
        if (metrics.pipelineState === 'halted')
            return 'critical';
        if (metrics.pipelineState === 'degraded')
            return 'warning';
        return 'healthy';
    };
    const getOpportunitiesHealthStatus = () => {
        if (metrics.totalOpportunities < 10)
            return 'warning';
        if (metrics.totalOpportunities > 300)
            return 'critical';
        return 'healthy';
    };
    const getMarketDataHealthStatus = () => {
        if (metrics.marketDataFreshness > 60)
            return 'critical';
        if (metrics.marketDataFreshness > 30)
            return 'warning';
        return 'healthy';
    };
    const actions = [
        {
            id: 'pipeline',
            label: 'View Pipeline',
            icon: Zap,
            path: '/pipeline',
        },
        {
            id: 'opportunities',
            label: 'View Opportunities',
            icon: Target,
            path: '/opportunities',
        },
        {
            id: 'risk',
            label: 'Open Risk Center',
            icon: AlertCircle,
            path: '/risk',
        },
        {
            id: 'execution',
            label: 'Open Execution',
            icon: Cpu,
            path: '/execution',
        },
        {
            id: 'settlement',
            label: 'Open Settlement',
            icon: CheckCircle,
            path: '/settlement',
        },
        {
            id: 'market',
            label: 'Open Market Data',
            icon: Database,
            path: '/market-data',
        },
        {
            id: 'compute',
            label: 'Open Compute',
            icon: Cpu,
            path: '/compute',
        },
    ];
    return (_jsxs(Layout, { onRefresh: refreshData, isLoading: loading, children: [_jsxs("div", { className: "space-y-8", children: [_jsxs("div", { children: [_jsx("h2", { className: "text-display-lg font-serif text-primary mb-2", children: "System Overview" }), _jsx("p", { className: "text-body-md text-on-surface-variant", children: "Monitor real-time metrics and take immediate action on any section" })] }), _jsxs("div", { className: "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-6 gap-4", children: [_jsx(IndicatorCard, { title: "Pipeline State", value: metrics.pipelineState.toUpperCase(), status: getPipelineHealthStatus(), statusLabel: metrics.pipelineState, description: getPipelineStatusDescription(), icon: Zap, onClick: () => navigate('/pipeline'), trend: { value: metrics.totalOpportunities - 50, direction: 'up' } }), _jsx(IndicatorCard, { title: "Total Opportunities", value: metrics.totalOpportunities, status: getOpportunitiesHealthStatus(), statusLabel: `${metrics.activeOpportunities} active`, description: `${metrics.activeOpportunities} actively processing`, icon: Target, onClick: () => navigate('/opportunities'), trend: { value: 12, direction: 'up' } }), _jsx(IndicatorCard, { title: "Risk Status", value: metrics.riskStatus.toUpperCase(), status: metrics.riskStatus === 'blocked' ? 'critical' : metrics.riskStatus === 'elevated' ? 'warning' : 'healthy', statusLabel: `${metrics.openBreakers} breaker${metrics.openBreakers !== 1 ? 's' : ''}`, description: getRiskStatusDescription(), icon: AlertCircle, onClick: () => navigate('/risk') }), _jsx(IndicatorCard, { title: "Execution Health", value: metrics.recentExecutions, status: metrics.executionHealth, statusLabel: `${metrics.recentExecutions} today`, description: getExecutionHealthDescription(), icon: Cpu, onClick: () => navigate('/execution'), trend: { value: 8, direction: 'up' } }), _jsx(IndicatorCard, { title: "Settlement Status", value: metrics.settlementStatus.toUpperCase(), status: metrics.settlementStatus, statusLabel: "Active", description: getSettlementStatusDescription(), icon: CheckCircle, onClick: () => navigate('/settlement') }), _jsx(IndicatorCard, { title: "Market Data Freshness", value: `${metrics.marketDataFreshness}s`, status: getMarketDataHealthStatus(), statusLabel: "age", description: `Updated ${new Date(metrics.lastMarketDataSample).toLocaleTimeString()}`, icon: Database, onClick: () => navigate('/market-data') })] }), _jsxs("div", { className: "bg-white rounded-lg p-6 border border-outline-variant/20 shadow-elevation-1", children: [_jsx("h3", { className: "text-headline-sm font-serif mb-6 text-primary", children: "Quick Navigation" }), _jsxs("div", { className: "flex items-center justify-between", children: [_jsx(ActionButtons, { actions: actions }), _jsxs("div", { className: "ml-4 flex items-center gap-2", children: [_jsx("button", { className: "btn-secondary", onClick: () => setShowTour(true), children: "Guided Tour" }), _jsx("button", { className: "btn-primary", onClick: () => { runDemo(); setShowTour(false); }, children: "Run Demo" }), _jsx("button", { className: "btn-primary", onClick: async () => { await runDemoAuto(); setShowTour(false); }, children: "Run Full Demo" })] })] })] }), _jsx(ActivityFeed, { activities: activities }), _jsxs("div", { className: "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4", children: [_jsxs("div", { className: "card", children: [_jsx("p", { className: "text-label-md text-on-surface-variant mb-2", children: "Active Opportunities" }), _jsx("p", { className: "text-headline-md font-serif text-primary mb-1", children: metrics.activeOpportunities }), _jsx("p", { className: "text-label-sm text-on-surface-variant", children: "Currently processing" })] }), _jsxs("div", { className: "card", children: [_jsx("p", { className: "text-label-md text-on-surface-variant mb-2", children: "Live Positions" }), _jsx("p", { className: "text-headline-md font-serif text-primary mb-1", children: metrics.livePositions }), _jsx("p", { className: "text-label-sm text-on-surface-variant", children: "Open trades" })] }), _jsxs("div", { className: "card", children: [_jsx("p", { className: "text-label-md text-on-surface-variant mb-2", children: "Open Breakers" }), _jsx("p", { className: "text-headline-md font-serif text-primary mb-1", children: metrics.openBreakers }), _jsx("p", { className: "text-label-sm text-on-surface-variant", children: "Risk controls" })] }), _jsxs("div", { className: "card", children: [_jsx("p", { className: "text-label-md text-on-surface-variant mb-2", children: "Recent Executions" }), _jsx("p", { className: "text-headline-md font-serif text-primary mb-1", children: metrics.recentExecutions }), _jsx("p", { className: "text-label-sm text-on-surface-variant", children: "In last 24h" })] })] })] }), showTour && (_jsx("div", { className: "fixed inset-0 bg-black/30 flex items-center justify-center z-50", children: _jsxs("div", { className: "card w-[560px] p-6", children: [_jsx("h3", { className: "text-headline-sm font-serif mb-3", children: "Quick Demo Tour" }), _jsxs("div", { className: "text-body-md mb-4", children: [tourStep === 0 && _jsxs("p", { children: ["Step 1: Open ", _jsx("strong", { children: "Opportunities" }), " and locate the seeded demo item ", _jsx("em", { children: "OPP-9999" }), "."] }), tourStep === 1 && _jsxs("p", { children: ["Step 2: Click ", _jsx("strong", { children: "Simulate" }), " to run a pre-flight check, then ", _jsx("strong", { children: "Approve" }), " to send to execution."] }), tourStep === 2 && _jsxs("p", { children: ["Step 3: Visit ", _jsx("strong", { children: "Execution" }), " to broadcast the tx, then ", _jsx("strong", { children: "Settlement" }), " to review the realized PnL and ledger export."] })] }), _jsxs("div", { className: "flex justify-between", children: [_jsx("div", { children: _jsx("button", { className: "btn-secondary mr-2", onClick: () => { if (tourStep > 0)
                                            setTourStep(tourStep - 1);
                                        else
                                            setShowTour(false); }, children: tourStep > 0 ? 'Back' : 'Close' }) }), _jsxs("div", { className: "flex items-center gap-2", children: [_jsx("button", { className: "btn-secondary", onClick: () => { runDemo(); setShowTour(false); }, children: "Skip and Run Demo" }), tourStep < 2 ? (_jsx("button", { className: "btn-primary", onClick: () => setTourStep(tourStep + 1), children: "Next" })) : (_jsx("button", { className: "btn-primary", onClick: () => { runDemo(); setShowTour(false); }, children: "Start Demo" }))] })] })] }) }))] }));
};
export default Dashboard;
//# sourceMappingURL=Dashboard.js.map