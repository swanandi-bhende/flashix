import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { Layout } from '@/components';
import { StatusBadge } from '@/components';
export const Settlement = () => {
    const navigate = useNavigate();
    const settlements = [
        {
            id: '1',
            tradeId: 'TRADE-001',
            amount: 45000,
            status: 'completed',
            timestamp: '1 hour ago',
        },
        {
            id: '2',
            tradeId: 'TRADE-002',
            amount: 38500,
            status: 'completed',
            timestamp: '2 hours ago',
        },
        {
            id: '3',
            tradeId: 'TRADE-003',
            amount: 52000,
            status: 'pending',
            timestamp: '15 minutes ago',
        },
    ];
    return (_jsx(Layout, { children: _jsxs("div", { className: "space-y-8", children: [_jsxs("div", { className: "flex items-center gap-4 mb-6", children: [_jsx("button", { onClick: () => navigate('/'), className: "p-2 hover:bg-surface-container rounded-lg transition-colors", children: _jsx(ArrowLeft, { className: "w-5 h-5" }) }), _jsxs("div", { children: [_jsx("h1", { className: "text-display-lg font-serif text-primary", children: "Settlement Center" }), _jsx("p", { className: "text-body-md text-on-surface-variant", children: "Monitor position repayment, ledger entries, and trade outcomes" })] })] }), _jsxs("div", { className: "grid grid-cols-1 md:grid-cols-3 gap-4 mb-6", children: [_jsxs("div", { className: "card", children: [_jsx("p", { className: "text-label-md text-on-surface-variant mb-2", children: "Settlement Status" }), _jsx(StatusBadge, { status: "healthy", label: "HEALTHY" }), _jsx("p", { className: "text-label-sm text-on-surface-variant mt-2", children: "All on schedule" })] }), _jsxs("div", { className: "card", children: [_jsx("p", { className: "text-label-md text-on-surface-variant mb-2", children: "Completed Today" }), _jsx("p", { className: "text-headline-md font-serif text-primary", children: "34" }), _jsx("p", { className: "text-label-sm text-on-surface-variant mt-2", children: "$1.2M settled" })] }), _jsxs("div", { className: "card", children: [_jsx("p", { className: "text-label-md text-on-surface-variant mb-2", children: "Ledger Balance" }), _jsx("p", { className: "text-headline-md font-serif text-primary", children: "$450K" }), _jsx("p", { className: "text-label-sm text-on-surface-variant mt-2", children: "Available funds" })] })] }), _jsxs("div", { className: "grid grid-cols-1 md:grid-cols-2 gap-6", children: [_jsxs("div", { className: "card", children: [_jsx("h2", { className: "text-headline-sm font-serif mb-4", children: "Repayment Status" }), _jsxs("div", { className: "space-y-4", children: [_jsxs("div", { children: [_jsxs("div", { className: "flex justify-between mb-2", children: [_jsx("span", { className: "text-body-md", children: "Pending Repayments" }), _jsx("span", { className: "font-semibold text-primary", children: "5" })] }), _jsx("div", { className: "w-full bg-surface-container rounded-full h-2", children: _jsx("div", { className: "bg-yellow-500 h-2 rounded-full", style: { width: '100%' } }) })] }), _jsxs("div", { children: [_jsxs("div", { className: "flex justify-between mb-2", children: [_jsx("span", { className: "text-body-md", children: "Total Amount" }), _jsx("span", { className: "font-semibold text-primary", children: "$125K" })] }), _jsx("p", { className: "text-label-sm text-on-surface-variant", children: "Expected completion in 4 hours" })] })] })] }), _jsxs("div", { className: "card", children: [_jsx("h2", { className: "text-headline-sm font-serif mb-4", children: "Ledger Summary" }), _jsxs("div", { className: "space-y-3", children: [_jsxs("div", { className: "flex justify-between", children: [_jsx("span", { className: "text-body-md", children: "Total Deposits" }), _jsx("span", { className: "font-semibold text-primary", children: "$5.2M" })] }), _jsxs("div", { className: "flex justify-between", children: [_jsx("span", { className: "text-body-md", children: "Total Withdrawals" }), _jsx("span", { className: "font-semibold text-primary", children: "$4.75M" })] }), _jsx("div", { className: "divider" }), _jsxs("div", { className: "flex justify-between", children: [_jsx("span", { className: "font-semibold text-body-md", children: "Net Balance" }), _jsx("span", { className: "font-semibold text-primary", children: "$450K" })] })] })] })] }), _jsxs("div", { className: "card", children: [_jsx("h2", { className: "text-headline-sm font-serif mb-6", children: "Recent Settlement Transactions" }), _jsx("div", { className: "overflow-x-auto", children: _jsxs("table", { className: "w-full", children: [_jsx("thead", { children: _jsxs("tr", { className: "border-b border-outline-variant/30", children: [_jsx("th", { className: "text-left py-3 px-4 text-label-md text-on-surface-variant", children: "Trade ID" }), _jsx("th", { className: "text-right py-3 px-4 text-label-md text-on-surface-variant", children: "Amount" }), _jsx("th", { className: "text-center py-3 px-4 text-label-md text-on-surface-variant", children: "Status" }), _jsx("th", { className: "text-right py-3 px-4 text-label-md text-on-surface-variant", children: "Time" })] }) }), _jsx("tbody", { children: settlements.map((settlement) => (_jsxs("tr", { className: "border-b border-outline-variant/20 hover:bg-surface-container transition-colors", children: [_jsx("td", { className: "py-4 px-4 text-body-md text-on-surface", children: settlement.tradeId }), _jsxs("td", { className: "py-4 px-4 text-right text-body-md font-semibold", children: ["$", settlement.amount.toLocaleString()] }), _jsx("td", { className: "py-4 px-4 text-center", children: _jsx("span", { className: `inline-flex items-center px-3 py-1 rounded-full text-label-sm font-semibold ${settlement.status === 'completed'
                                                            ? 'bg-green-100 text-green-900'
                                                            : 'bg-yellow-100 text-yellow-900'}`, children: settlement.status }) }), _jsx("td", { className: "py-4 px-4 text-right text-label-sm text-on-surface-variant", children: settlement.timestamp })] }, settlement.id))) })] }) })] })] }) }));
};
export default Settlement;
//# sourceMappingURL=Settlement.js.map