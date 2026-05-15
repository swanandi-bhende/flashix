import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { ArrowLeft, Activity, Brain, Filter, Search, Settings2, ShieldCheck, } from 'lucide-react';
import { Layout, StatusBadge } from '@/components';
const stageOrder = [
    'discovery',
    'filtering',
    'inference',
    'reasoning',
    'execution',
    'settlement',
];
const stageMeta = {
    discovery: {
        key: 'discovery',
        label: 'Discovery',
        worker: 'DiscoveryWorker-1',
        queue: 'opportunity-discovery-queue',
        logStream: 'discovery-events',
        description: 'Finds raw opportunities and incoming signals.',
        processedRecently: 482,
        latencyMs: 95,
        backlog: 12,
        status: 'healthy',
        nextStage: 'filtering',
        icon: Search,
    },
    filtering: {
        key: 'filtering',
        label: 'Filtering',
        worker: 'FilterWorker-2',
        queue: 'filtering-queue',
        logStream: 'filtering-events',
        description: 'Removes low-quality or invalid opportunities.',
        processedRecently: 366,
        latencyMs: 140,
        backlog: 8,
        status: 'healthy',
        nextStage: 'inference',
        icon: Filter,
    },
    inference: {
        key: 'inference',
        label: 'Inference',
        worker: 'InferenceEngine-TEE',
        queue: 'inference-queue',
        logStream: 'inference-events',
        description: 'Scores opportunities with model-assisted inference.',
        processedRecently: 248,
        latencyMs: 210,
        backlog: 19,
        status: 'warning',
        nextStage: 'reasoning',
        icon: Brain,
    },
    reasoning: {
        key: 'reasoning',
        label: 'Reasoning',
        worker: 'ReasoningOrchestrator-1',
        queue: 'reasoning-queue',
        logStream: 'reasoning-events',
        description: 'Applies policy, constraints, and decision logic.',
        processedRecently: 204,
        latencyMs: 275,
        backlog: 5,
        status: 'healthy',
        nextStage: 'execution',
        icon: Settings2,
    },
    execution: {
        key: 'execution',
        label: 'Execution',
        worker: 'ExecutionEngine-4',
        queue: 'execution-queue',
        logStream: 'execution-events',
        description: 'Sends transactions and tracks on-chain outcomes.',
        processedRecently: 146,
        latencyMs: 320,
        backlog: 14,
        status: 'warning',
        nextStage: 'settlement',
        icon: Activity,
    },
    settlement: {
        key: 'settlement',
        label: 'Settlement',
        worker: 'SettlementMonitor-2',
        queue: 'settlement-queue',
        logStream: 'settlement-events',
        description: 'Finalizes repayment state and completed trade records.',
        processedRecently: 138,
        latencyMs: 180,
        backlog: 3,
        status: 'healthy',
        icon: ShieldCheck,
    },
};
const sampleItems = [
    { id: 'OPP-1042', stage: 'discovery', note: 'New signal from market scanner' },
    { id: 'OPP-1039', stage: 'filtering', note: 'Awaiting quality checks' },
    { id: 'OPP-1031', stage: 'inference', note: 'Model score recalculating' },
    { id: 'OPP-1024', stage: 'reasoning', note: 'Policy gate in review' },
    { id: 'OPP-1017', stage: 'execution', note: 'Transaction broadcast pending' },
    { id: 'OPP-1004', stage: 'settlement', note: 'Awaiting ledger confirmation' },
];
const statusLabel = {
    healthy: 'Healthy',
    warning: 'Attention needed',
    critical: 'Urgent action required',
};
export const Pipeline = () => {
    const navigate = useNavigate();
    const params = useParams();
    const [searchParams, setSearchParams] = useSearchParams();
    const selectedStageKey = params.stage ?? 'discovery';
    const selectedItemId = searchParams.get('item') ?? sampleItems[0].id;
    const [livePulse, setLivePulse] = useState(0);
    useEffect(() => {
        const timer = window.setInterval(() => {
            setLivePulse((value) => value + 1);
        }, 5000);
        return () => window.clearInterval(timer);
    }, []);
    const selectedItem = sampleItems.find((item) => item.id === selectedItemId) ?? sampleItems[0];
    const selectedStageIndex = stageOrder.indexOf(selectedItem.stage);
    const selectedStage = stageMeta[selectedStageKey] ?? stageMeta.discovery;
    const highlightedPath = useMemo(() => {
        return stageOrder.map((stageKey, index) => ({
            stageKey,
            active: index <= selectedStageIndex,
            current: stageKey === selectedItem.stage,
            next: stageOrder[index + 1],
        }));
    }, [selectedItem.stage, selectedStageIndex]);
    const goToStage = (stageKey, focus) => {
        const path = `/pipeline/${stageKey}`;
        if (focus === 'queue') {
            navigate(`${path}?focus=queue`);
            return;
        }
        if (focus === 'logs') {
            navigate(`${path}?focus=logs`);
            return;
        }
        navigate(path);
    };
    const updateSelectedItem = (itemId) => {
        setSearchParams((current) => {
            current.set('item', itemId);
            return current;
        });
    };
    return (_jsx(Layout, { children: _jsxs("div", { className: "space-y-8", children: [_jsxs("div", { className: "flex items-center gap-4 mb-4", children: [_jsx("button", { onClick: () => navigate('/'), className: "p-2 hover:bg-surface-container rounded-lg transition-colors", children: _jsx(ArrowLeft, { className: "w-5 h-5" }) }), _jsxs("div", { children: [_jsx("h1", { className: "text-display-lg font-serif text-primary", children: "Pipeline Control" }), _jsx("p", { className: "text-body-md text-on-surface-variant", children: "Live operational flow from discovery to settlement" })] })] }), _jsxs("div", { className: "grid grid-cols-1 lg:grid-cols-[1.6fr_0.8fr] gap-6 items-start", children: [_jsxs("div", { className: "card space-y-6", children: [_jsxs("div", { className: "flex items-start justify-between gap-4 flex-wrap", children: [_jsxs("div", { children: [_jsx("h2", { className: "text-headline-sm font-serif text-primary", children: "Connected stage flow" }), _jsx("p", { className: "text-body-md text-on-surface-variant", children: "Discovery, filtering, inference, reasoning, execution, and settlement are shown in order with live handoff indicators." })] }), _jsxs("div", { className: "status-badge status-healthy", children: ["Live pulse ", livePulse] })] }), _jsx("div", { className: "grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 items-start", children: stageOrder.map((stageKey, index) => {
                                        const stage = stageMeta[stageKey];
                                        const selected = stageKey === selectedStageKey;
                                        const activePath = highlightedPath[index]?.active;
                                        const currentItem = selectedItem.stage === stageKey;
                                        return (_jsxs("div", { className: "flex flex-col h-full", children: [_jsxs("button", { onClick: () => goToStage(stage.key), className: `card text-left h-full transition-all hover:-translate-y-1 hover:shadow-elevation-2 ${selected ? 'ring-2 ring-primary/30 bg-surface-container-low' : ''} ${activePath ? 'border-primary/20' : ''}`, children: [_jsxs("div", { className: "flex items-start justify-between gap-3 mb-4", children: [_jsxs("div", { children: [_jsx("p", { className: "text-label-sm uppercase tracking-[0.08em] text-on-surface-variant", children: stage.label }), _jsx("h3", { className: "text-headline-sm font-serif text-primary mt-1 break-words leading-tight", children: stage.worker })] }), _jsx("div", { className: `p-3 rounded-lg ${stage.status === 'healthy' ? 'bg-green-100' : stage.status === 'warning' ? 'bg-yellow-100' : 'bg-red-100'}`, children: React.createElement(stage.icon, { className: 'w-5 h-5 text-primary' }) })] }), _jsx("p", { className: "text-body-md text-on-surface-variant mb-4", children: stage.description }), _jsxs("div", { className: "space-y-3", children: [_jsxs("div", { className: "flex items-center justify-between gap-3", children: [_jsx(StatusBadge, { status: stage.status, label: statusLabel[stage.status] }), _jsxs("span", { className: "text-label-sm text-on-surface-variant", children: [stage.backlog, " waiting"] })] }), _jsxs("div", { className: "grid grid-cols-2 gap-3 text-label-sm text-on-surface-variant", children: [_jsxs("div", { className: "rounded-lg bg-surface-container-low p-3", children: [_jsx("p", { className: "uppercase tracking-[0.05em]", children: "Throughput" }), _jsxs("p", { className: "mt-1 text-body-md text-primary", children: [stage.processedRecently, "/h"] })] }), _jsxs("div", { className: "rounded-lg bg-surface-container-low p-3", children: [_jsx("p", { className: "uppercase tracking-[0.05em]", children: "Latency" }), _jsxs("p", { className: "mt-1 text-body-md text-primary", children: [stage.latencyMs, " ms"] })] })] }), _jsxs("div", { className: "flex flex-wrap gap-2 text-label-sm text-on-surface-variant", children: [_jsxs("span", { className: "rounded-full bg-surface-container-low px-3 py-1", children: ["Queue: ", stage.queue] }), _jsxs("span", { className: "rounded-full bg-surface-container-low px-3 py-1", children: ["Worker: ", stage.worker] })] }), currentItem && (_jsxs("div", { className: "rounded-lg border border-primary/20 bg-primary/5 p-3", children: [_jsx("p", { className: "text-label-sm text-primary", children: "Selected item is here" }), _jsx("p", { className: "mt-1 text-body-md text-on-surface", children: selectedItem.id }), _jsxs("p", { className: "text-label-sm text-on-surface-variant", children: ["Next: ", stage.nextStage ? stageMeta[stage.nextStage].label : 'Complete'] })] }))] })] }), _jsxs("div", { className: "mt-3 flex flex-wrap gap-2", children: [_jsx("button", { onClick: () => goToStage(stage.key, 'queue'), className: "btn-secondary flex-1 min-w-[110px]", children: "View Queue" }), _jsx("button", { onClick: () => goToStage(stage.key, 'logs'), className: "btn-secondary flex-1 min-w-[110px]", children: "Open Logs" }), _jsx("button", { onClick: () => goToStage(stage.key), className: "btn-primary flex-1 min-w-[110px]", children: "Drill Down" })] })] }, stage.key));
                                    }) })] }), _jsxs("div", { className: "space-y-6 lg:sticky lg:top-24", children: [_jsxs("div", { className: "card space-y-4", children: [_jsx("h2", { className: "text-headline-sm font-serif text-primary", children: "Stage detail" }), _jsxs("div", { children: [_jsx("p", { className: "text-label-sm text-on-surface-variant uppercase tracking-[0.08em]", children: "Selected stage" }), _jsx("p", { className: "mt-1 text-headline-sm font-serif text-primary", children: selectedStage.label })] }), _jsxs("div", { className: "space-y-3", children: [_jsxs("div", { className: "rounded-lg bg-surface-container-low p-4", children: [_jsx("p", { className: "text-label-sm text-on-surface-variant", children: "Exact worker" }), _jsx("p", { className: "mt-1 text-body-md text-on-surface", children: selectedStage.worker })] }), _jsxs("div", { className: "rounded-lg bg-surface-container-low p-4", children: [_jsx("p", { className: "text-label-sm text-on-surface-variant", children: "Queue behind stage" }), _jsx("p", { className: "mt-1 text-body-md text-on-surface", children: selectedStage.queue })] }), _jsxs("div", { className: "rounded-lg bg-surface-container-low p-4", children: [_jsx("p", { className: "text-label-sm text-on-surface-variant", children: "Log stream" }), _jsx("p", { className: "mt-1 text-body-md text-on-surface", children: selectedStage.logStream })] })] }), _jsxs("div", { className: "grid grid-cols-2 gap-3", children: [_jsx("button", { className: "btn-secondary", onClick: () => navigate(`/pipeline/${selectedStage.key}?focus=queue`), children: "View Queue" }), _jsx("button", { className: "btn-secondary", onClick: () => navigate(`/pipeline/${selectedStage.key}?focus=logs`), children: "Open Logs" }), _jsx("button", { className: "btn-primary col-span-2", onClick: () => navigate(`/pipeline/${selectedStage.key}`), children: "Open worker detail" })] })] }), _jsxs("div", { className: "card space-y-4", children: [_jsx("h2", { className: "text-headline-sm font-serif text-primary", children: "Selected item path" }), _jsx("div", { className: "space-y-2", children: sampleItems.map((item) => {
                                                const active = item.id === selectedItem.id;
                                                return (_jsx("button", { onClick: () => updateSelectedItem(item.id), className: `w-full rounded-lg border px-4 py-3 text-left transition-colors ${active ? 'border-primary bg-primary/5' : 'border-outline-variant/30 hover:bg-surface-container-low'}`, children: _jsxs("div", { className: "flex items-center justify-between gap-4", children: [_jsxs("div", { children: [_jsx("p", { className: "text-label-md text-primary", children: item.id }), _jsx("p", { className: "text-label-sm text-on-surface-variant", children: item.note })] }), _jsxs("div", { className: "text-right", children: [_jsx("p", { className: "text-label-sm text-on-surface-variant", children: "Current stage" }), _jsx("p", { className: "text-body-md text-on-surface", children: stageMeta[item.stage].label })] })] }) }, item.id));
                                            }) }), _jsxs("div", { className: "rounded-lg bg-surface-container-low p-4", children: [_jsx("p", { className: "text-label-sm text-on-surface-variant uppercase tracking-[0.08em]", children: "Current path" }), _jsx("div", { className: "mt-3 flex flex-col gap-2", children: stageOrder.map((stageKey, index) => {
                                                        const stage = stageMeta[stageKey];
                                                        const isCurrent = stageKey === selectedItem.stage;
                                                        const isComplete = index <= selectedStageIndex;
                                                        return (_jsxs("div", { className: `flex items-center justify-between rounded-lg px-3 py-2 ${isCurrent ? 'bg-primary text-on-primary' : isComplete ? 'bg-white' : 'bg-transparent'}`, children: [_jsx("span", { className: "text-label-md", children: stage.label }), _jsx("span", { className: "text-label-sm", children: isCurrent ? 'Current' : isComplete ? 'Passed' : 'Next' })] }, stageKey));
                                                    }) })] })] }), _jsxs("div", { className: "card space-y-4", children: [_jsx("h2", { className: "text-headline-sm font-serif text-primary", children: "Operational answers" }), _jsxs("div", { className: "space-y-3 text-body-md text-on-surface-variant", children: [_jsxs("p", { children: ["Where is work now: ", selectedStage.label, " stage, with ", selectedStage.backlog, " waiting."] }), _jsxs("p", { children: ["What is blocked: ", selectedStage.status === 'healthy' ? 'Nothing in the selected stage.' : 'The selected stage needs attention.'] }), _jsxs("p", { children: ["Which queue is growing: ", selectedStage.queue, "."] }), _jsxs("p", { children: ["What action next: open the worker detail, queue, or logs for ", selectedStage.worker, "."] })] })] })] })] }), _jsxs("div", { className: "grid grid-cols-1 md:grid-cols-3 gap-6", children: [_jsxs("div", { className: "card", children: [_jsx("p", { className: "text-label-md text-on-surface-variant mb-2", children: "Recent throughput" }), _jsx("p", { className: "text-headline-md font-serif text-primary", children: "1,384" }), _jsx("p", { className: "text-label-sm text-on-surface-variant mt-2", children: "Across the full backend flow" })] }), _jsxs("div", { className: "card", children: [_jsx("p", { className: "text-label-md text-on-surface-variant mb-2", children: "Current backlog" }), _jsx("p", { className: "text-headline-md font-serif text-primary", children: "61" }), _jsx("p", { className: "text-label-sm text-on-surface-variant mt-2", children: "Mostly in inference and execution" })] }), _jsxs("div", { className: "card", children: [_jsx("p", { className: "text-label-md text-on-surface-variant mb-2", children: "End-to-end latency" }), _jsx("p", { className: "text-headline-md font-serif text-primary", children: "1.22s" }), _jsx("p", { className: "text-label-sm text-on-surface-variant mt-2", children: "Discovery through settlement" })] })] })] }) }));
};
export default Pipeline;
//# sourceMappingURL=Pipeline.js.map