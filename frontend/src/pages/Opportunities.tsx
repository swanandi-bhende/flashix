import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { Layout } from '@/components';
import { useDashboardStore } from '@/store';
import StatusBadge from '@/components/StatusBadge';

export const Opportunities: React.FC = () => {
  const navigate = useNavigate();
  const opportunities = useDashboardStore((s) => s.opportunities);
  const simulate = useDashboardStore((s) => s.simulateOpportunity);
  const approve = useDashboardStore((s) => s.approveOpportunity);
  const reject = useDashboardStore((s) => s.rejectOpportunity);
  const addActivity = useDashboardStore((s) => s.addActivity);
  const simulateMempoolEvents = useDashboardStore((s) => s.simulateMempoolEvents);

  const [simResult, setSimResult] = useState<{ id: string; result: string } | null>(null);
  const [traceView, setTraceView] = useState<{ id: string; trace: any[] } | null>(null);
  const [rejectPrompt, setRejectPrompt] = useState<{ id: string; open: boolean } | null>(null);
  const [rejectReason, setRejectReason] = useState('');

  const pendingCount = opportunities.filter((opp) => opp.status === 'pending').length;
  const executingCount = opportunities.filter((opp) => opp.status === 'executing').length;
  const rejectedCount = opportunities.filter((opp) => opp.status === 'rejected').length;
  const averageConfidence = opportunities.length
    ? opportunities.reduce((sum, opp) => sum + (opp.confidenceScore ?? 0), 0) / opportunities.length
    : 0;

  const onSimulate = async (id: string) => {
    const result = await simulate(id);
    setSimResult({ id, result });
    addActivity({ id: `sim-${id}`, type: 'execution', timestamp: new Date(), title: `Simulation ${result}`, description: `Simulation for ${id} returned ${result}`, status: 'healthy' });
  };

  const onApprove = (id: string) => {
    approve(id);
    addActivity({ id: `approve-${id}`, type: 'execution', timestamp: new Date(), title: `Approved ${id}`, description: `Operator approved ${id}`, status: 'healthy' });
  };

  const onReject = (id: string) => {
    if (!rejectPrompt) {
      setRejectPrompt({ id, open: true });
      setRejectReason('');
      return;
    }

    // handled by confirmReject
  };

  const confirmReject = () => {
    if (!rejectPrompt) return;
    reject(rejectPrompt.id, rejectReason || 'operator_rejected');
    addActivity({ id: `reject-${rejectPrompt.id}`, type: 'risk_event', timestamp: new Date(), title: `Rejected ${rejectPrompt.id}`, description: rejectReason || 'Rejected by operator', status: 'warning' });
    setRejectPrompt(null);
    setRejectReason('');
  };

  const onOpenTrace = (id: string) => {
    const o = opportunities.find((x) => x.id === id);
    setTraceView({ id, trace: o?.trace ?? [] });
  };

  return (
    <Layout>
      <div className="space-y-6">
        <div className="flex items-center gap-4 mb-2">
          <button onClick={() => navigate('/')} className="p-2 hover:bg-surface-container rounded-lg transition-colors">
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <h1 className="text-display-lg font-serif text-primary">Opportunities</h1>
            <p className="text-body-md text-on-surface-variant">Live queue of filtered trade candidates from mempool and cost engine</p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="card border-2 border-primary/20">
            <p className="text-label-md text-on-surface-variant mb-2">Queue size</p>
            <p className="text-display-sm font-serif text-primary">{opportunities.length}</p>
          </div>
          <div className="card border-2 border-green-200">
            <p className="text-label-md text-on-surface-variant mb-2">Pending</p>
            <p className="text-display-sm font-serif text-primary">{pendingCount}</p>
          </div>
          <div className="card border-2 border-blue-200">
            <p className="text-label-md text-on-surface-variant mb-2">Executing</p>
            <p className="text-display-sm font-serif text-primary">{executingCount}</p>
          </div>
          <div className="card border-2 border-purple-200">
            <p className="text-label-md text-on-surface-variant mb-2">Avg confidence</p>
            <p className="text-display-sm font-serif text-primary">{averageConfidence.toFixed(2)}</p>
            <p className="text-label-sm text-on-surface-variant mt-1">Rejected: {rejectedCount}</p>
          </div>
        </div>

        <div className="card border-2 border-primary/20 bg-primary/5">
          <div className="flex items-center justify-between gap-4 flex-wrap">
            <div>
              <p className="text-label-md text-on-surface-variant uppercase tracking-wider mb-2">Decision flow</p>
              <h2 className="text-headline-md font-serif">Every candidate now keeps a visible action trail.</h2>
            </div>
            <div className="flex items-center gap-3">
              <div className="text-label-md text-on-surface-variant mr-4">Open a row for the full decision screen and trace.</div>
              <div className="flex items-center gap-2">
                <button className="btn-secondary" onClick={() => simulateMempoolEvents(3)}>Simulate 3 Mempool Events</button>
                <button className="btn-secondary" onClick={() => simulateMempoolEvents(10)}>Simulate 10</button>
              </div>
            </div>
          </div>
        </div>

        <div className="card">
          <h2 className="text-headline-sm font-serif mb-4">Live Queue</h2>

          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-outline-variant/30 text-left">
                  <th className="py-3 px-4 text-label-sm">ID</th>
                  <th className="py-3 px-4 text-label-sm">Size</th>
                  <th className="py-3 px-4 text-label-sm">Expected Profit</th>
                  <th className="py-3 px-4 text-label-sm">Risk</th>
                  <th className="py-3 px-4 text-label-sm">Freshness</th>
                  <th className="py-3 px-4 text-label-sm">Disposition</th>
                  <th className="py-3 px-4 text-label-sm">Actions</th>
                </tr>
              </thead>
              <tbody>
                {opportunities.map((opp) => (
                  <tr key={opp.id} className="border-b border-outline-variant/20 hover:bg-surface-container transition-colors cursor-pointer" onClick={() => navigate(`/opportunity/${opp.id}`)}>
                    <td className="py-4 px-4 text-body-md">{opp.id}</td>
                    <td className="py-4 px-4 text-body-md">{(opp.expectedProfit / 10).toFixed(2)}</td>
                    <td className="py-4 px-4 text-body-md">${opp.expectedProfit}</td>
                    <td className="py-4 px-4 text-body-md">{opp.risk}</td>
                    <td className="py-4 px-4 text-body-md">{opp.freshnessSeconds ?? 0}s</td>
                    <td className="py-4 px-4 text-body-md">
                      <StatusBadge status={opp.status === 'pending' ? 'healthy' : opp.status === 'executing' ? 'warning' : 'critical'} label={opp.status} />
                      {opp.simulatedResult && (
                        <p className="mt-2 text-label-sm text-on-surface-variant">Simulation: <span className="font-semibold text-primary">{opp.simulatedResult.toUpperCase()}</span></p>
                      )}
                    </td>
                    <td className="py-4 px-4 text-body-md">
                      <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
                        <button className="btn-secondary" onClick={() => navigate(`/opportunity/${opp.id}`)}>View Details</button>
                        <button className="btn-secondary" onClick={() => onSimulate(opp.id)}>Simulate</button>
                        <button className="btn-primary" onClick={() => onApprove(opp.id)}>Approve</button>
                        <button className="btn-secondary" onClick={() => onReject(opp.id)}>Reject</button>
                        <button className="btn-secondary" onClick={() => onOpenTrace(opp.id)}>Open Trace</button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Simulation result modal */}
        {simResult && (
          <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
            <div className="card w-[520px]">
              <h3 className="text-headline-sm mb-2">Simulation Result</h3>
              <p className="text-body-md">Opportunity {simResult.id} simulation: {simResult.result}</p>
              <p className="text-label-sm text-on-surface-variant mt-2">The queue row keeps this result so the state is visible after you close the modal.</p>
              <div className="mt-4 flex justify-end gap-2">
                <button className="btn-secondary" onClick={() => setSimResult(null)}>Close</button>
              </div>
            </div>
          </div>
        )}

        {/* Trace modal */}
        {traceView && (
          <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
            <div className="card w-[720px] max-h-[70vh] overflow-auto">
              <h3 className="text-headline-sm mb-2">Trace: {traceView.id}</h3>
              <p className="text-label-sm text-on-surface-variant mb-3">This is the exact decision trail attached to the current queue item.</p>
              <div className="space-y-2">
                {traceView.trace.map((t: any, i: number) => (
                  <div key={i} className="p-3 border rounded-lg">
                    <p className="text-label-sm text-on-surface-variant">{t.step}</p>
                    <p className="text-body-md">{t.detail}</p>
                    <p className="text-label-sm text-on-surface-variant">{new Date(t.timestamp).toLocaleString()}</p>
                  </div>
                ))}
              </div>
              <div className="mt-4 flex justify-end gap-2">
                <button className="btn-secondary" onClick={() => setTraceView(null)}>Close</button>
              </div>
            </div>
          </div>
        )}

        {/* Reject prompt modal */}
        {rejectPrompt && (
          <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
            <div className="card w-[520px]">
              <h3 className="text-headline-sm mb-2">Reject Opportunity {rejectPrompt.id}</h3>
              <p className="text-label-sm text-on-surface-variant mb-3">Rejected opportunities stay auditable in the activity feed and queue state.</p>
              <textarea className="w-full p-3 border rounded" rows={4} value={rejectReason} onChange={(e) => setRejectReason(e.target.value)} placeholder="Rejection reason for audit" />
              <div className="mt-4 flex justify-end gap-2">
                <button className="btn-secondary" onClick={() => setRejectPrompt(null)}>Cancel</button>
                <button className="btn-primary" onClick={confirmReject}>Confirm Reject</button>
              </div>
            </div>
          </div>
        )}
      </div>
    </Layout>
  );
};

export default Opportunities;
