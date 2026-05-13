import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import React from 'react';
import { Circle, AlertTriangle, MoveRight, ShieldCheck, Workflow } from 'lucide-react';
import StatusBadge from './StatusBadge';
const getActivityIcon = (type) => {
    const icons = {
        opportunity_detected: MoveRight,
        risk_event: AlertTriangle,
        execution: Workflow,
        settlement: ShieldCheck,
        market_feed: Circle,
    };
    return icons[type];
};
const getActivityTypeLabel = (type) => {
    const labels = {
        opportunity_detected: 'Opportunity',
        risk_event: 'Risk Event',
        execution: 'Execution',
        settlement: 'Settlement',
        market_feed: 'Market Data',
    };
    return labels[type];
};
export const ActivityFeed = ({ activities, maxItems = 8 }) => {
    const displayedActivities = activities.slice(0, maxItems);
    const formatTime = (date) => {
        const now = new Date();
        const diff = now.getTime() - date.getTime();
        const minutes = Math.floor(diff / 60000);
        const hours = Math.floor(diff / 3600000);
        if (minutes < 1)
            return 'Just now';
        if (minutes < 60)
            return `${minutes}m ago`;
        if (hours < 24)
            return `${hours}h ago`;
        return date.toLocaleDateString();
    };
    return (_jsxs("div", { className: "card", children: [_jsx("h2", { className: "text-headline-sm font-serif mb-6", children: "Recent Activity" }), _jsx("div", { className: "space-y-4", children: displayedActivities.map((activity, index) => (_jsxs("div", { children: [_jsxs("div", { className: "flex gap-4", children: [_jsx("div", { className: "p-2 rounded-full bg-surface-container-low flex-shrink-0 text-primary", children: React.createElement(getActivityIcon(activity.type), { className: 'w-5 h-5' }) }), _jsxs("div", { className: "flex-1 min-w-0", children: [_jsxs("div", { className: "flex items-start justify-between gap-2 mb-1", children: [_jsxs("div", { children: [_jsx("p", { className: "text-label-md text-on-surface", children: activity.title }), _jsxs("p", { className: "text-label-sm text-on-surface-variant", children: [getActivityTypeLabel(activity.type), " \u00B7 ", formatTime(activity.timestamp)] })] }), _jsx(StatusBadge, { status: activity.status, label: activity.status })] }), _jsx("p", { className: "text-body-md text-on-surface-variant", children: activity.description })] })] }), index < displayedActivities.length - 1 && _jsx("div", { className: "divider my-4" })] }, activity.id))) })] }));
};
export default ActivityFeed;
//# sourceMappingURL=ActivityFeed.js.map