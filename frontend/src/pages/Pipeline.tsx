import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import {
  ArrowLeft,
  ArrowRight,
  Activity,
  Brain,
  Filter,
  Search,
  Settings2,
  ShieldCheck,
  type LucideIcon,
} from 'lucide-react';
import { Layout, StatusBadge } from '@/components';

type PipelineStageKey = 'discovery' | 'filtering' | 'inference' | 'reasoning' | 'execution' | 'settlement';
type PipelineStatus = 'healthy' | 'warning' | 'critical';

interface PipelineStage {
  key: PipelineStageKey;
  label: string;
  worker: string;
  queue: string;
  logStream: string;
  detailPath: string;
  queuePath: string;
  logPath: string;
  drillsPath: string;
  description: string;
  processedRecently: number;
  latencyMs: number;
  backlog: number;
  status: PipelineStatus;
  nextStage?: PipelineStageKey;
  icon: LucideIcon;
}

const stageOrder: PipelineStageKey[] = [
  'discovery',
  'filtering',
  'inference',
  'reasoning',
  'execution',
  'settlement',
];

const stageMeta: Record<PipelineStageKey, Omit<PipelineStage, 'detailPath' | 'queuePath' | 'logPath' | 'drillsPath'>> = {
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

const statusLabel: Record<PipelineStatus, string> = {
  healthy: 'Healthy',
  warning: 'Attention needed',
  critical: 'Urgent action required',
};

export const Pipeline: React.FC = () => {
  const navigate = useNavigate();
  const params = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedStageKey = (params.stage as PipelineStageKey | undefined) ?? 'discovery';
  const selectedItemId = searchParams.get('item') ?? sampleItems[0].id;

  const [livePulse, setLivePulse] = useState(0);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setLivePulse((value) => value + 1);
    }, 5000);

    return () => window.clearInterval(timer);
  }, []);

  const selectedItem = sampleItems.find((item) => item.id === selectedItemId) ?? sampleItems[0];
  const selectedStageIndex = stageOrder.indexOf(selectedItem.stage as PipelineStageKey);
  const selectedStage = stageMeta[selectedStageKey] ?? stageMeta.discovery;

  const highlightedPath = useMemo(() => {
    return stageOrder.map((stageKey, index) => ({
      stageKey,
      active: index <= selectedStageIndex,
      current: stageKey === selectedItem.stage,
      next: stageOrder[index + 1],
    }));
  }, [selectedItem.stage, selectedStageIndex]);

  const goToStage = (stageKey: PipelineStageKey, focus?: 'queue' | 'logs' | 'detail') => {
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

  const updateSelectedItem = (itemId: string) => {
    setSearchParams((current) => {
      current.set('item', itemId);
      return current;
    });
  };

  return (
    <Layout>
      <div className="space-y-8">
        <div className="flex items-center gap-4 mb-4">
          <button
            onClick={() => navigate('/')}
            className="p-2 hover:bg-surface-container rounded-lg transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <h1 className="text-display-lg font-serif text-primary">Pipeline Control</h1>
            <p className="text-body-md text-on-surface-variant">
              Live operational flow from discovery to settlement
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-[1.6fr_0.8fr] gap-6 items-start">
          <div className="card space-y-6">
            <div className="flex items-start justify-between gap-4 flex-wrap">
              <div>
                <h2 className="text-headline-sm font-serif text-primary">Connected stage flow</h2>
                <p className="text-body-md text-on-surface-variant">
                  Discovery, filtering, inference, reasoning, execution, and settlement are shown in order with live handoff indicators.
                </p>
              </div>
              <div className="status-badge status-healthy">
                Live pulse {livePulse}
              </div>
            </div>

            <div className="overflow-x-auto pb-2">
              <div className="min-w-[1120px] grid grid-cols-6 gap-4 items-stretch">
                {stageOrder.map((stageKey, index) => {
                  const stage = stageMeta[stageKey];
                  const selected = stageKey === selectedStageKey;
                  const activePath = highlightedPath[index]?.active;
                  const currentItem = selectedItem.stage === stageKey;

                  return (
                    <div key={stage.key} className="relative flex flex-col">
                      <button
                        onClick={() => goToStage(stage.key)}
                        className={`card text-left transition-all hover:-translate-y-1 hover:shadow-elevation-2 ${
                          selected ? 'ring-2 ring-primary/30 bg-surface-container-low' : ''
                        } ${activePath ? 'border-primary/20' : ''}`}
                      >
                        <div className="flex items-start justify-between gap-3 mb-4">
                          <div>
                            <p className="text-label-sm uppercase tracking-[0.08em] text-on-surface-variant">
                              {stage.label}
                            </p>
                            <h3 className="text-headline-sm font-serif text-primary mt-1">{stage.worker}</h3>
                          </div>
                          <div className={`p-3 rounded-lg ${stage.status === 'healthy' ? 'bg-green-100' : stage.status === 'warning' ? 'bg-yellow-100' : 'bg-red-100'}`}>
                            {React.createElement(stage.icon, { className: 'w-5 h-5 text-primary' })}
                          </div>
                        </div>

                        <p className="text-body-md text-on-surface-variant mb-4">{stage.description}</p>

                        <div className="space-y-3">
                          <div className="flex items-center justify-between gap-3">
                            <StatusBadge status={stage.status} label={statusLabel[stage.status]} />
                            <span className="text-label-sm text-on-surface-variant">{stage.backlog} waiting</span>
                          </div>

                          <div className="grid grid-cols-2 gap-3 text-label-sm text-on-surface-variant">
                            <div className="rounded-lg bg-surface-container-low p-3">
                              <p className="uppercase tracking-[0.05em]">Throughput</p>
                              <p className="mt-1 text-body-md text-primary">{stage.processedRecently}/h</p>
                            </div>
                            <div className="rounded-lg bg-surface-container-low p-3">
                              <p className="uppercase tracking-[0.05em]">Latency</p>
                              <p className="mt-1 text-body-md text-primary">{stage.latencyMs} ms</p>
                            </div>
                          </div>

                          <div className="flex flex-wrap gap-2 text-label-sm text-on-surface-variant">
                            <span className="rounded-full bg-surface-container-low px-3 py-1">Queue: {stage.queue}</span>
                            <span className="rounded-full bg-surface-container-low px-3 py-1">Worker: {stage.worker}</span>
                          </div>

                          {currentItem && (
                            <div className="rounded-lg border border-primary/20 bg-primary/5 p-3">
                              <p className="text-label-sm text-primary">Selected item is here</p>
                              <p className="mt-1 text-body-md text-on-surface">{selectedItem.id}</p>
                              <p className="text-label-sm text-on-surface-variant">Next: {stage.nextStage ? stageMeta[stage.nextStage].label : 'Complete'}</p>
                            </div>
                          )}
                        </div>
                      </button>

                      {index < stageOrder.length - 1 && (
                        <div className="hidden xl:flex absolute right-[-28px] top-1/2 -translate-y-1/2 items-center text-primary/50 z-10">
                          <ArrowRight className="w-6 h-6" />
                        </div>
                      )}

                      <div className="mt-3 flex flex-wrap gap-2">
                        <button
                          onClick={() => goToStage(stage.key, 'queue')}
                          className="btn-secondary flex-1 min-w-[110px]"
                        >
                          View Queue
                        </button>
                        <button
                          onClick={() => goToStage(stage.key, 'logs')}
                          className="btn-secondary flex-1 min-w-[110px]"
                        >
                          Open Logs
                        </button>
                        <button
                          onClick={() => goToStage(stage.key)}
                          className="btn-primary flex-1 min-w-[110px]"
                        >
                          Drill Down
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          <div className="space-y-6">
            <div className="card space-y-4">
              <h2 className="text-headline-sm font-serif text-primary">Stage detail</h2>
              <div>
                <p className="text-label-sm text-on-surface-variant uppercase tracking-[0.08em]">Selected stage</p>
                <p className="mt-1 text-headline-sm font-serif text-primary">{selectedStage.label}</p>
              </div>

              <div className="space-y-3">
                <div className="rounded-lg bg-surface-container-low p-4">
                  <p className="text-label-sm text-on-surface-variant">Exact worker</p>
                  <p className="mt-1 text-body-md text-on-surface">{selectedStage.worker}</p>
                </div>
                <div className="rounded-lg bg-surface-container-low p-4">
                  <p className="text-label-sm text-on-surface-variant">Queue behind stage</p>
                  <p className="mt-1 text-body-md text-on-surface">{selectedStage.queue}</p>
                </div>
                <div className="rounded-lg bg-surface-container-low p-4">
                  <p className="text-label-sm text-on-surface-variant">Log stream</p>
                  <p className="mt-1 text-body-md text-on-surface">{selectedStage.logStream}</p>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <button className="btn-secondary" onClick={() => navigate(`/pipeline/${selectedStage.key}?focus=queue`)}>
                  View Queue
                </button>
                <button className="btn-secondary" onClick={() => navigate(`/pipeline/${selectedStage.key}?focus=logs`)}>
                  Open Logs
                </button>
                <button className="btn-primary col-span-2" onClick={() => navigate(`/pipeline/${selectedStage.key}`)}>
                  Open worker detail
                </button>
              </div>
            </div>

            <div className="card space-y-4">
              <h2 className="text-headline-sm font-serif text-primary">Selected item path</h2>
              <div className="space-y-2">
                {sampleItems.map((item) => {
                  const active = item.id === selectedItem.id;
                  return (
                    <button
                      key={item.id}
                      onClick={() => updateSelectedItem(item.id)}
                      className={`w-full rounded-lg border px-4 py-3 text-left transition-colors ${
                        active ? 'border-primary bg-primary/5' : 'border-outline-variant/30 hover:bg-surface-container-low'
                      }`}
                    >
                      <div className="flex items-center justify-between gap-4">
                        <div>
                          <p className="text-label-md text-primary">{item.id}</p>
                          <p className="text-label-sm text-on-surface-variant">{item.note}</p>
                        </div>
                        <div className="text-right">
                          <p className="text-label-sm text-on-surface-variant">Current stage</p>
                          <p className="text-body-md text-on-surface">{stageMeta[item.stage as PipelineStageKey].label}</p>
                        </div>
                      </div>
                    </button>
                  );
                })}
              </div>

              <div className="rounded-lg bg-surface-container-low p-4">
                <p className="text-label-sm text-on-surface-variant uppercase tracking-[0.08em]">Current path</p>
                <div className="mt-3 flex flex-col gap-2">
                  {stageOrder.map((stageKey, index) => {
                    const stage = stageMeta[stageKey];
                    const isCurrent = stageKey === selectedItem.stage;
                    const isComplete = index <= selectedStageIndex;

                    return (
                      <div key={stageKey} className={`flex items-center justify-between rounded-lg px-3 py-2 ${isCurrent ? 'bg-primary text-on-primary' : isComplete ? 'bg-white' : 'bg-transparent'}`}>
                        <span className="text-label-md">{stage.label}</span>
                        <span className="text-label-sm">{isCurrent ? 'Current' : isComplete ? 'Passed' : 'Next'}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>

            <div className="card space-y-4">
              <h2 className="text-headline-sm font-serif text-primary">Operational answers</h2>
              <div className="space-y-3 text-body-md text-on-surface-variant">
                <p>Where is work now: {selectedStage.label} stage, with {selectedStage.backlog} waiting.</p>
                <p>What is blocked: {selectedStage.status === 'healthy' ? 'Nothing in the selected stage.' : 'The selected stage needs attention.'}</p>
                <p>Which queue is growing: {selectedStage.queue}.</p>
                <p>What action next: open the worker detail, queue, or logs for {selectedStage.worker}.</p>
              </div>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="card">
            <p className="text-label-md text-on-surface-variant mb-2">Recent throughput</p>
            <p className="text-headline-md font-serif text-primary">1,384</p>
            <p className="text-label-sm text-on-surface-variant mt-2">Across the full backend flow</p>
          </div>

          <div className="card">
            <p className="text-label-md text-on-surface-variant mb-2">Current backlog</p>
            <p className="text-headline-md font-serif text-primary">61</p>
            <p className="text-label-sm text-on-surface-variant mt-2">Mostly in inference and execution</p>
          </div>

          <div className="card">
            <p className="text-label-md text-on-surface-variant mb-2">End-to-end latency</p>
            <p className="text-headline-md font-serif text-primary">1.22s</p>
            <p className="text-label-sm text-on-surface-variant mt-2">Discovery through settlement</p>
          </div>
        </div>
      </div>
    </Layout>
  );
};

export default Pipeline;
