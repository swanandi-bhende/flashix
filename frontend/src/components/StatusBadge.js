import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
export const StatusBadge = ({ status, label }) => {
    const statusClasses = {
        healthy: 'status-healthy',
        warning: 'status-warning',
        critical: 'status-critical',
    };
    return (_jsxs("span", { className: `status-badge ${statusClasses[status]}`, children: [_jsx("span", { className: `w-2 h-2 rounded-full`, style: {
                    backgroundColor: status === 'healthy' ? '#10b981' : status === 'warning' ? '#f59e0b' : '#ef4444'
                } }), label] }));
};
export default StatusBadge;
//# sourceMappingURL=StatusBadge.js.map