import React, { useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Layout } from '@/components';
import { useDashboardStore } from '@/store';
import StatusBadge from '@/components/StatusBadge';

export const OpportunityDetail: React.FC = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const getOpportunity = useDashboardStore((s) => s.getOpportunity);
  const opp = getOpportunity(id ?? '');

  const whySection = useMemo(() => {
    if (!opp) return null;
    return (
      <div className="space-y-3">
        <p className="text-label-sm text-on-surface-variant">Signal origin</p>
        <p className="text-body-md">Source: {opp.source}</p>
        <p className="text-label-sm text-on-surface-variant">Detected at</p>
        <p className="text-body-md">{new Date(opp.detectionTime).toLocaleString()}</p>
      </div>
    );
  }, [opp]);

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

  return (
    <Layout>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-display-lg font-serif text-primary">Opportunity {opp.id}</h1>
            <p className="text-body-md text-on-surface-variant">Detailed view and next-step controls</p>
          </div>
          <div>
            <StatusBadge status={opp.status === 'pending' ? 'healthy' : opp.status === 'executing' ? 'warning' : 'critical'} label={opp.status} />
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="card">
            <h2 className="text-headline-sm font-serif mb-3">Why this trade exists</h2>
            {whySection}
            <div className="mt-4">
              <p className="text-label-sm text-on-surface-variant">Estimated spread</p>
              <p className="text-body-md">{(opp.expectedProfit / 100).toFixed(2)}%</p>
            </div>
            <div className="mt-3">
              <p className="text-label-sm text-on-surface-variant">Confidence / risk</p>
              <p className="text-body-md">Score: {(1 - opp.risk).toFixed(2)} · Risk: {opp.risk}</p>
            </div>
          </div>

          <div className="card">
            <h2 className="text-headline-sm font-serif mb-3">Cost analysis</h2>
            <p className="text-body-md">Estimated costs and gas: ${Math.round(opp.expectedProfit * 0.05)}</p>
            <p className="text-label-sm text-on-surface-variant mt-2">Net expected profit: ${opp.expectedProfit - Math.round(opp.expectedProfit * 0.05)}</p>

            <div className="mt-4">
              <p className="text-label-sm text-on-surface-variant">Simulation</p>
              <p className="text-body-md">Last simulation result: {opp.simulatedResult ?? 'not run'}</p>
            </div>
          </div>

          <div className="card">
            <h2 className="text-headline-sm font-serif mb-3">Next steps</h2>
            <p className="text-body-md">Approve to move into execution, Reject to remove from the active path, or run a simulation to re-evaluate.</p>
            <div className="mt-4 grid grid-cols-1 gap-2">
              <button className="btn-primary">Approve</button>
              <button className="btn-secondary">Simulate</button>
              <button className="btn-secondary">Open Trace</button>
            </div>
          </div>
        </div>

        <div className="card">
          <h2 className="text-headline-sm font-serif mb-3">Trace</h2>
          <div className="space-y-2">
            {opp.trace?.map((t: { step: string; detail: string; timestamp: Date }, i: number) => (
              <div key={i} className="p-3 border rounded-lg">
                <p className="text-label-sm text-on-surface-variant">{t.step}</p>
                <p className="text-body-md">{t.detail}</p>
                <p className="text-label-sm text-on-surface-variant">{new Date(t.timestamp).toLocaleString()}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </Layout>
  );
};

export default OpportunityDetail;
