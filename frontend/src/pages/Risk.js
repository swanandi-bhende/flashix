import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { Layout } from '@/components';
import { StatusBadge } from '@/components';
export const Risk = () => {
    const navigate = useNavigate();
    const riskEvents = [
        {
            id: '1',
            severity: 'high',
            category: 'Slippage',
            description: 'ETH/USDC slippage exceeded 0.5%',
            timestamp: '5 minutes ago',
        },
        {
            id: '2',
            severity: 'medium',
            category: 'Liquidity',
            description: 'Trading pair volume dropped 30%',
            timestamp: '12 minutes ago',
        },
        {
            id: '3',
            severity: 'low',
            category: 'Latency',
            description: 'Market feed delay detected',
            timestamp: '25 minutes ago',
        },
    ];
    const getSeverityColor = (severity) => {
        switch (severity) {
            case 'high':
            case 'critical':
                return 'bg-error-container text-on-error-container';
            case 'medium':
                return 'bg-yellow-100 text-yellow-900';
            case 'low':
                return 'bg-blue-100 text-blue-900';
            default:
                return 'bg-gray-100 text-gray-900';
        }
    };
    return (_jsx(Layout, { children: _jsxs("div", { className: "space-y-8", children: [_jsxs("div", { className: "flex items-center gap-4 mb-6", children: [_jsx("button", { onClick: () => navigate('/'), className: "p-2 hover:bg-surface-container rounded-lg transition-colors", children: _jsx(ArrowLeft, { className: "w-5 h-5" }) }), _jsxs("div", { children: [_jsx("h1", { className: "text-display-lg font-serif text-primary", children: "Risk Center" }), _jsx("p", { className: "text-body-md text-on-surface-variant", children: "Monitor risk events, breakers, and system safety limits" })] })] }), _jsxs("div", { className: "grid grid-cols-1 md:grid-cols-3 gap-4 mb-6", children: [_jsxs("div", { className: "card", children: [_jsx("p", { className: "text-label-md text-on-surface-variant mb-2", children: "Overall Risk Status" }), _jsx(StatusBadge, { status: "warning", label: "ELEVATED" }), _jsx("p", { className: "text-label-sm text-on-surface-variant mt-2", children: "Minor events detected" })] }), _jsxs("div", { className: "card", children: [_jsx("p", { className: "text-label-md text-on-surface-variant mb-2", children: "Active Breakers" }), _jsx("p", { className: "text-headline-md font-serif text-error", children: "2" }), _jsx("p", { className: "text-label-sm text-on-surface-variant mt-2", children: "Slippage, Liquidity" })] }), _jsxs("div", { className: "card", children: [_jsx("p", { className: "text-label-md text-on-surface-variant mb-2", children: "Triggered Today" }), _jsx("p", { className: "text-headline-md font-serif text-primary", children: "5" }), _jsx("p", { className: "text-label-sm text-on-surface-variant mt-2", children: "All resolved" })] })] }), _jsxs("div", { className: "card", children: [_jsx("h2", { className: "text-headline-sm font-serif mb-6", children: "Recent Risk Events" }), _jsx("div", { className: "space-y-4", children: riskEvents.map((event) => (_jsxs("div", { className: `p-4 rounded-lg border border-outline-variant/30 ${getSeverityColor(event.severity)}`, children: [_jsxs("div", { className: "flex justify-between items-start mb-2", children: [_jsxs("div", { children: [_jsx("p", { className: "text-label-md font-semibold", children: event.category }), _jsx("p", { className: "text-label-sm opacity-80 mt-1", children: event.description })] }), _jsx("span", { className: "text-label-sm font-semibold uppercase", children: event.severity })] }), _jsx("p", { className: "text-label-sm opacity-60", children: event.timestamp })] }, event.id))) })] }), _jsxs("div", { className: "card", children: [_jsx("h2", { className: "text-headline-sm font-serif mb-6", children: "Risk Configuration" }), _jsxs("div", { className: "grid grid-cols-1 md:grid-cols-2 gap-6", children: [_jsxs("div", { children: [_jsx("p", { className: "text-label-md text-on-surface-variant mb-2", children: "Max Slippage" }), _jsx("p", { className: "text-headline-md font-serif text-primary", children: "0.5%" }), _jsx("p", { className: "text-label-sm text-on-surface-variant mt-1", children: "Current: 0.48%" })] }), _jsxs("div", { children: [_jsx("p", { className: "text-label-md text-on-surface-variant mb-2", children: "Min Liquidity" }), _jsx("p", { className: "text-headline-md font-serif text-primary", children: "$500K" }), _jsx("p", { className: "text-label-sm text-on-surface-variant mt-1", children: "Current: $1.2M" })] }), _jsxs("div", { children: [_jsx("p", { className: "text-label-md text-on-surface-variant mb-2", children: "Max Position Size" }), _jsx("p", { className: "text-headline-md font-serif text-primary", children: "$1M" }), _jsx("p", { className: "text-label-sm text-on-surface-variant mt-1", children: "Current: $450K" })] }), _jsxs("div", { children: [_jsx("p", { className: "text-label-md text-on-surface-variant mb-2", children: "Max Daily Loss" }), _jsx("p", { className: "text-headline-md font-serif text-primary", children: "$50K" }), _jsx("p", { className: "text-label-sm text-on-surface-variant mt-1", children: "Current: -$12K" })] })] })] })] }) }));
};
export default Risk;
//# sourceMappingURL=Risk.js.map