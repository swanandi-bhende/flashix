import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useNavigate } from 'react-router-dom';
import { RefreshCw } from 'lucide-react';
export const Header = ({ onRefresh, isLoading = false }) => {
    const navigate = useNavigate();
    return (_jsx("header", { className: "sticky top-0 z-40 bg-white border-b border-outline-variant/20 shadow-elevation-1", children: _jsx("div", { className: "container-padding py-4", children: _jsxs("div", { className: "flex items-center justify-between", children: [_jsxs("div", { className: "cursor-pointer hover:opacity-80 transition-opacity", onClick: () => navigate('/'), children: [_jsx("h1", { className: "text-headline-md font-serif text-primary", children: "Flashix" }), _jsx("p", { className: "text-label-sm text-on-surface-variant", children: "Arbitrage Dashboard" })] }), _jsx("button", { onClick: onRefresh, disabled: isLoading, className: `p-2 rounded-lg bg-primary/10 hover:bg-primary/20 transition-colors ${isLoading ? 'animate-spin' : ''}`, children: _jsx(RefreshCw, { className: "w-5 h-5 text-primary" }) })] }) }) }));
};
export default Header;
//# sourceMappingURL=Header.js.map