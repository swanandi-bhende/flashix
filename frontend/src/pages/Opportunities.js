import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { Layout } from '@/components';
import { useDashboardStore } from '@/store';
import StatusBadge from '@/components/StatusBadge';
export const Opportunities = () => {
    const navigate = useNavigate();
    const opportunities = useDashboardStore((s) => s.opportunities);
    const simulate = useDashboardStore((s) => s.simulateOpportunity);
    const approve = useDashboardStore((s) => s.approveOpportunity);
    const reject = useDashboardStore((s) => s.rejectOpportunity);
    const addActivity = useDashboardStore((s) => s.addActivity);
    const simulateMempoolEvents = useDashboardStore((s) => s.simulateMempoolEvents);
    const [simResult, setSimResult] = useState(null);
    const [traceView, setTraceView] = useState(null);
    const [rejectPrompt, setRejectPrompt] = useState(null);
    const [rejectReason, setRejectReason] = useState('');
    const pendingCount = opportunities.filter((opp) => opp.status === 'pending').length;
    const executingCount = opportunities.filter((opp) => opp.status === 'executing').length;
    const rejectedCount = opportunities.filter((opp) => opp.status === 'rejected').length;
    const averageConfidence = opportunities.length
        ? opportunities.reduce((sum, opp) => sum + (opp.confidenceScore ?? 0), 0) / opportunities.length
        : 0;
    const onSimulate = async (id) => {
        const result = await simulate(id);
        setSimResult({ id, result });
        addActivity({ id: `sim-${id}`, type: 'execution', timestamp: new Date(), title: `Simulation ${result}`, description: `Simulation for ${id} returned ${result}`, status: 'healthy' });
    };
    const onApprove = (id) => {
        approve(id);
        addActivity({ id: `approve-${id}`, type: 'execution', timestamp: new Date(), title: `Approved ${id}`, description: `Operator approved ${id}`, status: 'healthy' });
    };
    const onReject = (id) => {
        if (!rejectPrompt) {
            setRejectPrompt({ id, open: true });
            setRejectReason('');
            return;
        }
        // handled by confirmReject
    };
    const confirmReject = () => {
        if (!rejectPrompt)
            return;
        reject(rejectPrompt.id, rejectReason || 'operator_rejected');
        addActivity({ id: `reject-${rejectPrompt.id}`, type: 'risk_event', timestamp: new Date(), title: `Rejected ${rejectPrompt.id}`, description: rejectReason || 'Rejected by operator', status: 'warning' });
        setRejectPrompt(null);
        setRejectReason('');
    };
    const onOpenTrace = (id) => {
        const o = opportunities.find((x) => x.id === id);
        setTraceView({ id, trace: o?.trace ?? [] });
    };
    return (_jsx(Layout, { children: _jsxs("div", { className: "space-y-6", children: [_jsxs("div", { className: "flex items-center gap-4 mb-2", children: [_jsx("button", { onClick: () => navigate('/'), className: "p-2 hover:bg-surface-container rounded-lg transition-colors", children: _jsx(ArrowLeft, { className: "w-5 h-5" }) }), _jsxs("div", { children: [_jsx("h1", { className: "text-display-lg font-serif text-primary", children: "Opportunities" }), _jsx("p", { className: "text-body-md text-on-surface-variant", children: "Live queue of filtered trade candidates from mempool and cost engine" })] })] }), _jsxs("div", { className: "grid grid-cols-1 md:grid-cols-4 gap-4", children: [_jsxs("div", { className: "card border-2 border-primary/20", children: [_jsx("p", { className: "text-label-md text-on-surface-variant mb-2", children: "Queue size" }), _jsx("p", { className: "text-display-sm font-serif text-primary", children: opportunities.length })] }), _jsxs("div", { className: "card border-2 border-green-200", children: [_jsx("p", { className: "text-label-md text-on-surface-variant mb-2", children: "Pending" }), _jsx("p", { className: "text-display-sm font-serif text-primary", children: pendingCount })] }), _jsxs("div", { className: "card border-2 border-blue-200", children: [_jsx("p", { className: "text-label-md text-on-surface-variant mb-2", children: "Executing" }), _jsx("p", { className: "text-display-sm font-serif text-primary", children: executingCount })] }), _jsxs("div", { className: "card border-2 border-purple-200", children: [_jsx("p", { className: "text-label-md text-on-surface-variant mb-2", children: "Avg confidence" }), _jsx("p", { className: "text-display-sm font-serif text-primary", children: averageConfidence.toFixed(2) }), _jsxs("p", { className: "text-label-sm text-on-surface-variant mt-1", children: ["Rejected: ", rejectedCount] })] })] }), _jsx("div", { className: "card border-2 border-primary/20 bg-primary/5", children: _jsxs("div", { className: "flex items-center justify-between gap-4 flex-wrap", children: [_jsxs("div", { children: [_jsx("p", { className: "text-label-md text-on-surface-variant uppercase tracking-wider mb-2", children: "Decision flow" }), _jsx("h2", { className: "text-headline-md font-serif", children: "Every candidate now keeps a visible action trail." })] }), _jsxs("div", { className: "flex items-center gap-3", children: [_jsx("div", { className: "text-label-md text-on-surface-variant mr-4", children: "Open a row for the full decision screen and trace." }), _jsxs("div", { className: "flex items-center gap-2", children: [_jsx("button", { className: "btn-secondary", onClick: () => simulateMempoolEvents(3), children: "Simulate 3 Mempool Events" }), _jsx("button", { className: "btn-secondary", onClick: () => simulateMempoolEvents(10), children: "Simulate 10" })] })] })] }) }), _jsxs("div", { className: "card", children: [_jsx("h2", { className: "text-headline-sm font-serif mb-4", children: "Live Queue" }), _jsx("div", { className: "overflow-x-auto", children: _jsxs("table", { className: "w-full", children: [_jsx("thead", { children: _jsxs("tr", { className: "border-b border-outline-variant/30 text-left", children: [_jsx("th", { className: "py-3 px-4 text-label-sm", children: "ID" }), _jsx("th", { className: "py-3 px-4 text-label-sm", children: "Size" }), _jsx("th", { className: "py-3 px-4 text-label-sm", children: "Expected Profit" }), _jsx("th", { className: "py-3 px-4 text-label-sm", children: "Risk" }), _jsx("th", { className: "py-3 px-4 text-label-sm", children: "Freshness" }), _jsx("th", { className: "py-3 px-4 text-label-sm", children: "Disposition" }), _jsx("th", { className: "py-3 px-4 text-label-sm", children: "Actions" })] }) }), _jsx("tbody", { children: opportunities.map((opp) => (_jsxs("tr", { className: "border-b border-outline-variant/20 hover:bg-surface-container transition-colors cursor-pointer", onClick: () => navigate(`/opportunity/${opp.id}`), children: [_jsx("td", { className: "py-4 px-4 text-body-md", children: opp.id }), _jsx("td", { className: "py-4 px-4 text-body-md", children: (opp.expectedProfit / 10).toFixed(2) }), _jsxs("td", { className: "py-4 px-4 text-body-md", children: ["$", opp.expectedProfit] }), _jsx("td", { className: "py-4 px-4 text-body-md", children: opp.risk }), _jsxs("td", { className: "py-4 px-4 text-body-md", children: [opp.freshnessSeconds ?? 0, "s"] }), _jsxs("td", { className: "py-4 px-4 text-body-md", children: [_jsx(StatusBadge, { status: opp.status === 'pending' ? 'healthy' : opp.status === 'executing' ? 'warning' : 'critical', label: opp.status }), opp.simulatedResult && (_jsxs("p", { className: "mt-2 text-label-sm text-on-surface-variant", children: ["Simulation: ", _jsx("span", { className: "font-semibold text-primary", children: opp.simulatedResult.toUpperCase() })] }))] }), _jsx("td", { className: "py-4 px-4 text-body-md", children: _jsxs("div", { className: "flex items-center gap-2", onClick: (e) => e.stopPropagation(), children: [_jsx("button", { className: "btn-secondary", onClick: () => navigate(`/opportunity/${opp.id}`), children: "View Details" }), _jsx("button", { className: "btn-secondary", onClick: () => onSimulate(opp.id), children: "Simulate" }), _jsx("button", { className: "btn-primary", onClick: () => onApprove(opp.id), children: "Approve" }), _jsx("button", { className: "btn-secondary", onClick: () => onReject(opp.id), children: "Reject" }), _jsx("button", { className: "btn-secondary", onClick: () => onOpenTrace(opp.id), children: "Open Trace" })] }) })] }, opp.id))) })] }) })] }), simResult && (_jsx("div", { className: "fixed inset-0 bg-black/30 flex items-center justify-center z-50", children: _jsxs("div", { className: "card w-[520px]", children: [_jsx("h3", { className: "text-headline-sm mb-2", children: "Simulation Result" }), _jsxs("p", { className: "text-body-md", children: ["Opportunity ", simResult.id, " simulation: ", simResult.result] }), _jsx("p", { className: "text-label-sm text-on-surface-variant mt-2", children: "The queue row keeps this result so the state is visible after you close the modal." }), _jsx("div", { className: "mt-4 flex justify-end gap-2", children: _jsx("button", { className: "btn-secondary", onClick: () => setSimResult(null), children: "Close" }) })] }) })), traceView && (_jsx("div", { className: "fixed inset-0 bg-black/30 flex items-center justify-center z-50", children: _jsxs("div", { className: "card w-[720px] max-h-[70vh] overflow-auto", children: [_jsxs("h3", { className: "text-headline-sm mb-2", children: ["Trace: ", traceView.id] }), _jsx("p", { className: "text-label-sm text-on-surface-variant mb-3", children: "This is the exact decision trail attached to the current queue item." }), _jsx("div", { className: "space-y-2", children: traceView.trace.map((t, i) => (_jsxs("div", { className: "p-3 border rounded-lg", children: [_jsx("p", { className: "text-label-sm text-on-surface-variant", children: t.step }), _jsx("p", { className: "text-body-md", children: t.detail }), _jsx("p", { className: "text-label-sm text-on-surface-variant", children: new Date(t.timestamp).toLocaleString() })] }, i))) }), _jsx("div", { className: "mt-4 flex justify-end gap-2", children: _jsx("button", { className: "btn-secondary", onClick: () => setTraceView(null), children: "Close" }) })] }) })), rejectPrompt && (_jsx("div", { className: "fixed inset-0 bg-black/30 flex items-center justify-center z-50", children: _jsxs("div", { className: "card w-[520px]", children: [_jsxs("h3", { className: "text-headline-sm mb-2", children: ["Reject Opportunity ", rejectPrompt.id] }), _jsx("p", { className: "text-label-sm text-on-surface-variant mb-3", children: "Rejected opportunities stay auditable in the activity feed and queue state." }), _jsx("textarea", { className: "w-full p-3 border rounded", rows: 4, value: rejectReason, onChange: (e) => setRejectReason(e.target.value), placeholder: "Rejection reason for audit" }), _jsxs("div", { className: "mt-4 flex justify-end gap-2", children: [_jsx("button", { className: "btn-secondary", onClick: () => setRejectPrompt(null), children: "Cancel" }), _jsx("button", { className: "btn-primary", onClick: confirmReject, children: "Confirm Reject" })] })] }) }))] }) }));
};
export default Opportunities;
//# sourceMappingURL=Opportunities.js.map