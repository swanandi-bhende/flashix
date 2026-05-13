import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Layout } from '@/components';
import { useDashboardStore } from '@/store';
import StatusBadge from '@/components/StatusBadge';

export const OpportunityDetail: React.FC = () => {
  const { id } = useParams();
  const navigate = useNavigate();

  const getOpportunity = useDashboardStore((s) => s.getOpportunity);
  const simulate = useDashboardStore((s) => s.simulateOpportunity);
  const approve = useDashboardStore((s) => s.approveOpportunity);
  const reject = useDashboardStore((s) => s.rejectOpportunity);
  const addActivity = useDashboardStore((s) => s.addActivity);

  const opp = getOpportunity(id ?? '');

  const [activeTab, setActiveTab] = React.useState<'price' | 'cost' | 'confidence' | 'risk' | 'profit' | 'raw'>('price');
  const [simRunning, setSimRunning] = React.useState(false);
  const [rejectPromptOpen, setRejectPromptOpen] = React.useState(false);
  const [rejectReason, setRejectReason] = React.useState('');

  React.useEffect(() => {
    // keep context; could pre-run a quick simulate when page loads if desired
  }, [id]);

  if (!opp) {
    return (
      <Layout>
        <div className="card">
          <p className="text-body-md">Opportunity not found</p>
          <button className="btn-secondary mt-4" onClick={() => navigate('/opportunities')}>Back to queue</button>
        </div>
      </Layout>
    );
  }

  const runSimulation = async () => {
    setSimRunning(true);
    const result = await simulate(opp.id);
    addActivity({ id: `sim-${opp.id}`, type: 'execution', timestamp: new Date(), title: `Simulation ${result}`, description: `Simulation returned ${result}`, status: 'healthy' });
    setSimRunning(false);
  };

  const sendToExecution = () => {
    approve(opp.id);
    addActivity({ id: `exec-${opp.id}`, type: 'execution', timestamp: new Date(), title: `Sent ${opp.id} to execution`, description: 'Operator sent to execution', status: 'healthy' });
    navigate('/opportunities');
  };

  const markIgnored = (reason: string) => {
    reject(opp.id, reason);
    addActivity({ id: `rej-${opp.id}`, type: 'risk_event', timestamp: new Date(), title: `Ignored ${opp.id}`, description: reason, status: 'warning' });
    navigate('/opportunities');
  };

  return (
    <Layout>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-display-lg font-serif text-primary">Opportunity {opp.id}</h1>
            <p className="text-body-md text-on-surface-variant">Decision screen — evaluate the trade and choose an action</p>
          </div>
          <div>
            <StatusBadge status={opp.status === 'pending' ? 'healthy' : opp.status === 'executing' ? 'warning' : 'critical'} label={opp.status} />
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-3 items-center">
          <button className={`px-3 py-2 rounded ${activeTab === 'price' ? 'bg-primary text-on-primary' : 'bg-surface-container'}`} onClick={() => setActiveTab('price')}>Price Spread</button>
          <button className={`px-3 py-2 rounded ${activeTab === 'cost' ? 'bg-primary text-on-primary' : 'bg-surface-container'}`} onClick={() => setActiveTab('cost')}>Cost Breakdown</button>
          <button className={`px-3 py-2 rounded ${activeTab === 'confidence' ? 'bg-primary text-on-primary' : 'bg-surface-container'}`} onClick={() => setActiveTab('confidence')}>Confidence</button>
          <button className={`px-3 py-2 rounded ${activeTab === 'risk' ? 'bg-primary text-on-primary' : 'bg-surface-container'}`} onClick={() => setActiveTab('risk')}>Risk Checks</button>
          <button className={`px-3 py-2 rounded ${activeTab === 'profit' ? 'bg-primary text-on-primary' : 'bg-surface-container'}`} onClick={() => setActiveTab('profit')}>Expected Profit</button>
          <button className={`px-3 py-2 rounded ${activeTab === 'raw' ? 'bg-primary text-on-primary' : 'bg-surface-container'}`} onClick={() => setActiveTab('raw')}>Raw Signal</button>
        </div>

        <div className="card">
          {activeTab === 'price' && (
            <div>
              <h2 className="text-headline-sm font-serif mb-2">Price Spread</h2>
              <p className="text-label-sm text-on-surface-variant">Market pair</p>
              <p className="text-body-md mb-2">{opp.pair}</p>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <p className="text-label-sm text-on-surface-variant">Source prices</p>
                  <ul className="mt-2">
                    {opp.sourcePrices?.map((p, i) => (
                      <li key={i} className="text-body-md">{p.exchange}: {p.price}</li>
                    ))}
                  </ul>
                </div>
                <div>
                  <p className="text-label-sm text-on-surface-variant">Target prices</p>
                  <ul className="mt-2">
                    {opp.targetPrices?.map((p, i) => (
                      <li key={i} className="text-body-md">{p.exchange}: {p.price}</li>
                    ))}
                  </ul>
                </div>
              </div>

              <div className="mt-4">
                <p className="text-label-sm text-on-surface-variant">Spread</p>
                <p className="text-headline-sm font-serif">{opp.spreadPct?.toFixed(3)}%</p>
              </div>
            </div>
          )}

          {activeTab === 'cost' && (
            <div>
              <h2 className="text-headline-sm font-serif mb-2">Cost Breakdown</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div>
                  <p className="text-label-sm text-on-surface-variant">Gas Cost</p>
                  <p className="text-body-md">${opp.gasCost}</p>
                </div>
                <div>
                  <p className="text-label-sm text-on-surface-variant">Flashloan Cost</p>
                  <p className="text-body-md">${opp.flashloanCost}</p>
                </div>
                <div>
                  <p className="text-label-sm text-on-surface-variant">Slippage Estimate</p>
                  <p className="text-body-md">{(opp.slippageEstimate ?? 0) * 100}%</p>
                </div>
                <div>
                  <p className="text-label-sm text-on-surface-variant">Execution Overhead</p>
                  <p className="text-body-md">${opp.executionOverhead}</p>
                </div>
                <div>
                  <p className="text-label-sm text-on-surface-variant">Fees</p>
                  <p className="text-body-md">${opp.fees}</p>
                </div>
              </div>

              <div className="mt-4">
                <p className="text-label-sm text-on-surface-variant">Net expected profit after costs</p>
                <p className="text-headline-sm font-serif">${(opp.expectedProfit - ((opp.gasCost ?? 0) + (opp.flashloanCost ?? 0) + (opp.fees ?? 0))).toLocaleString()}</p>
              </div>
            </div>
          )}

          {activeTab === 'confidence' && (
            <div>
              <h2 className="text-headline-sm font-serif mb-2">Confidence Score</h2>
              <p className="text-body-md">Score: {(opp.confidenceScore ?? 0).toFixed(2)} ({(opp.confidenceScore ?? 0) > 0.8 ? 'High' : (opp.confidenceScore ?? 0) > 0.6 ? 'Medium' : 'Low'})</p>
              <div className="mt-3">
                <p className="text-label-sm text-on-surface-variant">Factors</p>
                <ul className="mt-2">
                  {opp.confidenceFactors?.map((f, i) => <li key={i} className="text-body-md">{f}</li>)}
                </ul>
              </div>
            </div>
          )}

          {activeTab === 'risk' && (
            <div>
              <h2 className="text-headline-sm font-serif mb-2">Risk Checks</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div>
                  <p className="text-label-sm text-on-surface-variant">Circuit Breaker</p>
                  <p className="text-body-md">{opp.riskChecks?.breakerTriggered ? 'Triggered' : 'OK'}</p>
                </div>
                <div>
                  <p className="text-label-sm text-on-surface-variant">Collateral</p>
                  <p className="text-body-md">{opp.riskChecks?.collateralOk ? 'OK' : 'Insufficient'}</p>
                </div>
                <div>
                  <p className="text-label-sm text-on-surface-variant">Slippage Limit</p>
                  <p className="text-body-md">{opp.riskChecks?.slippageLimitOk ? 'OK' : 'May violate'}</p>
                </div>
                <div>
                  <p className="text-label-sm text-on-surface-variant">Exposure</p>
                  <p className="text-body-md">{opp.riskChecks?.exposureOk ? 'OK' : 'Too large'}</p>
                </div>
              </div>

              {opp.riskChecks?.warnings && opp.riskChecks.warnings.length > 0 && (
                <div className="mt-3">
                  <p className="text-label-sm text-on-surface-variant">Warnings</p>
                  <ul className="mt-2">
                    {opp.riskChecks.warnings.map((w, i) => <li key={i} className="text-body-md">{w}</li>)}
                  </ul>
                </div>
              )}
            </div>
          )}

          {activeTab === 'profit' && (
            <div>
              <h2 className="text-headline-sm font-serif mb-2">Expected Profit</h2>
              <p className="text-label-sm text-on-surface-variant">Gross profit</p>
              <p className="text-headline-sm font-serif">${opp.expectedProfit}</p>
              <p className="text-label-sm text-on-surface-variant mt-2">Net (after shown costs)</p>
              <p className="text-body-md">${(opp.expectedProfit - ((opp.gasCost ?? 0) + (opp.flashloanCost ?? 0) + (opp.fees ?? 0))).toLocaleString()}</p>
            </div>
          )}

          {activeTab === 'raw' && (
            <div>
              <h2 className="text-headline-sm font-serif mb-2">Raw Signal Payload</h2>
              <pre className="p-3 bg-surface-container-low rounded text-sm overflow-auto">{JSON.stringify(opp.rawPayload, null, 2)}</pre>
            </div>
          )}
        </div>

        {/* Fixed action controls */}
        <div className="fixed bottom-6 right-6 z-50 flex gap-3">
          <button className="btn-secondary" onClick={() => runSimulation()} disabled={simRunning}>{simRunning ? 'Running...' : 'Run Again'}</button>
          <button className="btn-primary" onClick={() => sendToExecution()}>Send to Execution</button>
          <button className="btn-secondary" onClick={() => setRejectPromptOpen(true)}>Mark Ignored</button>
        </div>

        {/* Reject modal */}
        {rejectPromptOpen && (
          <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
            <div className="card w-[520px]">
              <h3 className="text-headline-sm mb-2">Mark {opp.id} Ignored</h3>
              <textarea className="w-full p-3 border rounded" rows={4} value={rejectReason} onChange={(e) => setRejectReason(e.target.value)} placeholder="Reason for ignoring (audit)" />
              <div className="mt-4 flex justify-end gap-2">
                <button className="btn-secondary" onClick={() => setRejectPromptOpen(false)}>Cancel</button>
                <button className="btn-primary" onClick={() => { markIgnored(rejectReason || 'ignored by operator'); setRejectPromptOpen(false); }}>Confirm</button>
              </div>
            </div>
          </div>
        )}
      </div>
    </Layout>
  );
};

export default OpportunityDetail;
