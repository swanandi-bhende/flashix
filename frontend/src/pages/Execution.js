import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { Layout } from '@/components';
export const Execution = () => {
    const navigate = useNavigate();
    const recentExecutions = [
        {
            id: '1',
            txHash: '0x1234...5678',
            pair: 'ETH/USDC',
            status: 'confirmed',
            gasCost: 120,
            profit: 2450,
            timestamp: '2 minutes ago',
        },
        {
            id: '2',
            txHash: '0x9abc...def0',
            pair: 'DAI/USDC',
            status: 'confirmed',
            gasCost: 95,
            profit: 1850,
            timestamp: '8 minutes ago',
        },
        {
            id: '3',
            txHash: '0x5def...1234',
            pair: 'USDT/USDC',
            status: 'failed',
            gasCost: 85,
            profit: 0,
            timestamp: '18 minutes ago',
        },
    ];
    const getStatusBadgeClass = (status) => {
        switch (status) {
            case 'confirmed':
                return 'bg-green-100 text-green-900';
            case 'pending':
                return 'bg-yellow-100 text-yellow-900';
            case 'failed':
                return 'bg-red-100 text-red-900';
            default:
                return 'bg-gray-100 text-gray-900';
        }
    };
    return (_jsx(Layout, { children: _jsxs("div", { className: "space-y-8", children: [_jsxs("div", { className: "flex items-center gap-4 mb-6", children: [_jsx("button", { onClick: () => navigate('/'), className: "p-2 hover:bg-surface-container rounded-lg transition-colors", children: _jsx(ArrowLeft, { className: "w-5 h-5" }) }), _jsxs("div", { children: [_jsx("h1", { className: "text-display-lg font-serif text-primary", children: "Execution History" }), _jsx("p", { className: "text-body-md text-on-surface-variant", children: "Track all executed trades, gas costs, and profitability" })] })] }), _jsxs("div", { className: "grid grid-cols-1 md:grid-cols-4 gap-4 mb-6", children: [_jsxs("div", { className: "card", children: [_jsx("p", { className: "text-label-md text-on-surface-variant mb-2", children: "Executed Today" }), _jsx("p", { className: "text-headline-md font-serif text-primary", children: "142" }), _jsx("p", { className: "text-label-sm text-on-surface-variant mt-2", children: "Success rate: 94.4%" })] }), _jsxs("div", { className: "card", children: [_jsx("p", { className: "text-label-md text-on-surface-variant mb-2", children: "Total Profit" }), _jsx("p", { className: "text-headline-md font-serif text-primary", children: "$45.8K" }), _jsx("p", { className: "text-label-sm text-on-surface-variant mt-2", children: "Net of gas costs" })] }), _jsxs("div", { className: "card", children: [_jsx("p", { className: "text-label-md text-on-surface-variant mb-2", children: "Avg Gas Cost" }), _jsx("p", { className: "text-headline-md font-serif text-primary", children: "$108" }), _jsx("p", { className: "text-label-sm text-on-surface-variant mt-2", children: "Current: $95-120" })] }), _jsxs("div", { className: "card", children: [_jsx("p", { className: "text-label-md text-on-surface-variant mb-2", children: "Failed Executions" }), _jsx("p", { className: "text-headline-md font-serif text-error", children: "8" }), _jsx("p", { className: "text-label-sm text-on-surface-variant mt-2", children: "5.6% failure rate" })] })] }), _jsxs("div", { className: "card", children: [_jsx("h2", { className: "text-headline-sm font-serif mb-6", children: "Recent Executions" }), _jsx("div", { className: "overflow-x-auto", children: _jsxs("table", { className: "w-full", children: [_jsx("thead", { children: _jsxs("tr", { className: "border-b border-outline-variant/30", children: [_jsx("th", { className: "text-left py-3 px-4 text-label-md text-on-surface-variant", children: "TX Hash" }), _jsx("th", { className: "text-left py-3 px-4 text-label-md text-on-surface-variant", children: "Pair" }), _jsx("th", { className: "text-right py-3 px-4 text-label-md text-on-surface-variant", children: "Gas Cost" }), _jsx("th", { className: "text-right py-3 px-4 text-label-md text-on-surface-variant", children: "Profit" }), _jsx("th", { className: "text-center py-3 px-4 text-label-md text-on-surface-variant", children: "Status" }), _jsx("th", { className: "text-right py-3 px-4 text-label-md text-on-surface-variant", children: "Time" })] }) }), _jsx("tbody", { children: recentExecutions.map((exec) => (_jsxs("tr", { className: "border-b border-outline-variant/20 hover:bg-surface-container transition-colors", children: [_jsx("td", { className: "py-4 px-4 font-body-md text-primary cursor-pointer hover:underline", children: exec.txHash }), _jsx("td", { className: "py-4 px-4 text-body-md", children: exec.pair }), _jsxs("td", { className: "py-4 px-4 text-right text-body-md", children: ["$", exec.gasCost] }), _jsx("td", { className: "py-4 px-4 text-right", children: _jsxs("span", { className: exec.profit > 0 ? 'text-green-600 font-semibold' : 'text-gray-600', children: ["$", exec.profit] }) }), _jsx("td", { className: "py-4 px-4 text-center", children: _jsx("span", { className: `inline-flex items-center px-3 py-1 rounded-full text-label-sm font-semibold ${getStatusBadgeClass(exec.status)}`, children: exec.status }) }), _jsx("td", { className: "py-4 px-4 text-right text-label-sm text-on-surface-variant", children: exec.timestamp })] }, exec.id))) })] }) })] })] }) }));
};
export default Execution;
//# sourceMappingURL=Execution.js.map