import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { Layout } from '@/components';
import { StatusBadge } from '@/components';
export const MarketData = () => {
    const navigate = useNavigate();
    const feeds = [
        {
            id: '1',
            name: 'Uniswap V3 USDC Swap',
            status: 'healthy',
            lastUpdate: '2 seconds ago',
            samples: 45000,
        },
        {
            id: '2',
            name: 'Curve 3CRV Pool',
            status: 'healthy',
            lastUpdate: '5 seconds ago',
            samples: 32000,
        },
        {
            id: '3',
            name: 'Balancer Weighted Pool',
            status: 'warning',
            lastUpdate: '45 seconds ago',
            samples: 18000,
        },
        {
            id: '4',
            name: 'AAVE LendingPool',
            status: 'healthy',
            lastUpdate: '3 seconds ago',
            samples: 22500,
        },
    ];
    return (_jsx(Layout, { children: _jsxs("div", { className: "space-y-8", children: [_jsxs("div", { className: "flex items-center gap-4 mb-6", children: [_jsx("button", { onClick: () => navigate('/'), className: "p-2 hover:bg-surface-container rounded-lg transition-colors", children: _jsx(ArrowLeft, { className: "w-5 h-5" }) }), _jsxs("div", { children: [_jsx("h1", { className: "text-display-lg font-serif text-primary", children: "Market Data Feeds" }), _jsx("p", { className: "text-body-md text-on-surface-variant", children: "Monitor real-time price feeds, latency, and data quality" })] })] }), _jsxs("div", { className: "grid grid-cols-1 md:grid-cols-3 gap-4 mb-6", children: [_jsxs("div", { className: "card", children: [_jsx("p", { className: "text-label-md text-on-surface-variant mb-2", children: "Overall Health" }), _jsx(StatusBadge, { status: "healthy", label: "HEALTHY" }), _jsx("p", { className: "text-label-sm text-on-surface-variant mt-2", children: "All feeds operational" })] }), _jsxs("div", { className: "card", children: [_jsx("p", { className: "text-label-md text-on-surface-variant mb-2", children: "Active Feeds" }), _jsx("p", { className: "text-headline-md font-serif text-primary", children: "4/4" }), _jsx("p", { className: "text-label-sm text-on-surface-variant mt-2", children: "100% uptime" })] }), _jsxs("div", { className: "card", children: [_jsx("p", { className: "text-label-md text-on-surface-variant mb-2", children: "Total Samples" }), _jsx("p", { className: "text-headline-md font-serif text-primary", children: "117.5K" }), _jsx("p", { className: "text-label-sm text-on-surface-variant mt-2", children: "Last 24 hours" })] })] }), _jsxs("div", { className: "card", children: [_jsx("h2", { className: "text-headline-sm font-serif mb-6", children: "Price Feeds" }), _jsx("div", { className: "grid grid-cols-1 md:grid-cols-2 gap-4", children: feeds.map((feed) => (_jsxs("div", { className: "p-4 border border-outline-variant/20 rounded-lg hover:shadow-elevation-1 transition-all", children: [_jsxs("div", { className: "flex justify-between items-start mb-3", children: [_jsx("div", { children: _jsx("h3", { className: "text-body-md text-on-surface", children: feed.name }) }), _jsx(StatusBadge, { status: feed.status === 'healthy' ? 'healthy' : 'warning', label: feed.status })] }), _jsxs("div", { className: "space-y-2 text-label-sm", children: [_jsxs("div", { className: "flex justify-between", children: [_jsx("span", { className: "text-on-surface-variant", children: "Last Update" }), _jsx("span", { className: "text-on-surface", children: feed.lastUpdate })] }), _jsxs("div", { className: "flex justify-between", children: [_jsx("span", { className: "text-on-surface-variant", children: "Samples" }), _jsx("span", { className: "text-on-surface", children: feed.samples.toLocaleString() })] })] }), _jsx("div", { className: "mt-3 pt-3 border-t border-outline-variant/20", children: _jsx("div", { className: "w-full bg-surface-container rounded-full h-2", children: _jsx("div", { className: "bg-primary h-2 rounded-full", style: { width: feed.status === 'healthy' ? '100%' : '70%' } }) }) })] }, feed.id))) })] }), _jsxs("div", { className: "grid grid-cols-1 md:grid-cols-2 gap-6", children: [_jsxs("div", { className: "card", children: [_jsx("h2", { className: "text-headline-sm font-serif mb-4", children: "Feed Latency" }), _jsxs("div", { className: "space-y-3", children: [_jsxs("div", { className: "flex justify-between items-center", children: [_jsx("span", { className: "text-body-md", children: "Avg Latency" }), _jsx("span", { className: "text-headline-md font-serif text-primary", children: "125ms" })] }), _jsxs("div", { className: "flex justify-between items-center", children: [_jsx("span", { className: "text-body-md", children: "P95 Latency" }), _jsx("span", { className: "text-headline-md font-serif text-primary", children: "340ms" })] }), _jsxs("div", { className: "flex justify-between items-center", children: [_jsx("span", { className: "text-body-md", children: "Max Latency" }), _jsx("span", { className: "text-headline-md font-serif text-primary", children: "890ms" })] }), _jsx("p", { className: "text-label-sm text-on-surface-variant", children: "Within acceptable thresholds" })] })] }), _jsxs("div", { className: "card", children: [_jsx("h2", { className: "text-headline-sm font-serif mb-4", children: "Data Quality" }), _jsxs("div", { className: "space-y-3", children: [_jsxs("div", { className: "flex justify-between items-center", children: [_jsx("span", { className: "text-body-md", children: "Missing Updates" }), _jsx("span", { className: "text-headline-md font-serif text-green-600", children: "0" })] }), _jsxs("div", { className: "flex justify-between items-center", children: [_jsx("span", { className: "text-body-md", children: "Stale Data" }), _jsx("span", { className: "text-headline-md font-serif text-green-600", children: "0" })] }), _jsxs("div", { className: "flex justify-between items-center", children: [_jsx("span", { className: "text-body-md", children: "Quality Score" }), _jsx("span", { className: "text-headline-md font-serif text-primary", children: "99.9%" })] }), _jsx("p", { className: "text-label-sm text-on-surface-variant", children: "Excellent data consistency" })] })] })] })] }) }));
};
export default MarketData;
//# sourceMappingURL=MarketData.js.map