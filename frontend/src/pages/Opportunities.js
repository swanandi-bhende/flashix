import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { Layout } from '@/components';
export const Opportunities = () => {
    const navigate = useNavigate();
    const mockOpportunities = [
        {
            id: '1',
            pair: 'ETH/USDC',
            expectedProfit: 2450,
            risk: 0.45,
            status: 'executing',
            detectedAt: '2 minutes ago',
        },
        {
            id: '2',
            pair: 'DAI/USDC',
            expectedProfit: 1850,
            risk: 0.32,
            status: 'pending',
            detectedAt: '5 minutes ago',
        },
        {
            id: '3',
            pair: 'WBTC/BTC',
            expectedProfit: 3200,
            risk: 0.68,
            status: 'pending',
            detectedAt: '12 minutes ago',
        },
    ];
    const getStatusColor = (status) => {
        switch (status) {
            case 'executing':
                return 'bg-blue-100 text-blue-900';
            case 'pending':
                return 'bg-yellow-100 text-yellow-900';
            case 'completed':
                return 'bg-green-100 text-green-900';
            default:
                return 'bg-gray-100 text-gray-900';
        }
    };
    return (_jsx(Layout, { children: _jsxs("div", { className: "space-y-8", children: [_jsxs("div", { className: "flex items-center gap-4 mb-6", children: [_jsx("button", { onClick: () => navigate('/'), className: "p-2 hover:bg-surface-container rounded-lg transition-colors", children: _jsx(ArrowLeft, { className: "w-5 h-5" }) }), _jsxs("div", { children: [_jsx("h1", { className: "text-display-lg font-serif text-primary", children: "Opportunities Queue" }), _jsx("p", { className: "text-body-md text-on-surface-variant", children: "All detected arbitrage opportunities with profit expectations" })] })] }), _jsxs("div", { className: "grid grid-cols-1 md:grid-cols-3 gap-4 mb-6", children: [_jsxs("div", { className: "card", children: [_jsx("p", { className: "text-label-md text-on-surface-variant mb-2", children: "Total Detected" }), _jsx("p", { className: "text-headline-md font-serif text-primary", children: "247" })] }), _jsxs("div", { className: "card", children: [_jsx("p", { className: "text-label-md text-on-surface-variant mb-2", children: "Currently Active" }), _jsx("p", { className: "text-headline-md font-serif text-primary", children: "12" })] }), _jsxs("div", { className: "card", children: [_jsx("p", { className: "text-label-md text-on-surface-variant mb-2", children: "Pending Execution" }), _jsx("p", { className: "text-headline-md font-serif text-primary", children: "8" })] })] }), _jsxs("div", { className: "card", children: [_jsx("h2", { className: "text-headline-sm font-serif mb-6", children: "Active Opportunities" }), _jsx("div", { className: "overflow-x-auto", children: _jsxs("table", { className: "w-full", children: [_jsx("thead", { children: _jsxs("tr", { className: "border-b border-outline-variant/30", children: [_jsx("th", { className: "text-left py-3 px-4 text-label-md text-on-surface-variant", children: "Pair" }), _jsx("th", { className: "text-right py-3 px-4 text-label-md text-on-surface-variant", children: "Expected Profit" }), _jsx("th", { className: "text-right py-3 px-4 text-label-md text-on-surface-variant", children: "Risk %" }), _jsx("th", { className: "text-center py-3 px-4 text-label-md text-on-surface-variant", children: "Status" }), _jsx("th", { className: "text-right py-3 px-4 text-label-md text-on-surface-variant", children: "Detected" })] }) }), _jsx("tbody", { children: mockOpportunities.map((opp) => (_jsxs("tr", { className: "border-b border-outline-variant/20 hover:bg-surface-container transition-colors", children: [_jsx("td", { className: "py-4 px-4 text-body-md text-on-surface", children: opp.pair }), _jsx("td", { className: "py-4 px-4 text-right", children: _jsxs("span", { className: "text-body-md text-primary", children: ["$", opp.expectedProfit] }) }), _jsxs("td", { className: "py-4 px-4 text-right text-body-md", children: [opp.risk, "%"] }), _jsx("td", { className: "py-4 px-4 text-center", children: _jsx("span", { className: `inline-flex items-center px-3 py-1 rounded-full text-label-sm font-semibold ${getStatusColor(opp.status)}`, children: opp.status }) }), _jsx("td", { className: "py-4 px-4 text-right text-label-sm text-on-surface-variant", children: opp.detectedAt })] }, opp.id))) })] }) })] })] }) }));
};
export default Opportunities;
//# sourceMappingURL=Opportunities.js.map