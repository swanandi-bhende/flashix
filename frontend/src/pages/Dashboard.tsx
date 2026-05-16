import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Zap,
  Target,
  AlertCircle,
  Cpu,
  CheckCircle,
  Database,
} from 'lucide-react';
import { Layout, IndicatorCard, ActionButtons, ActivityFeed } from '@/components';
import { useDashboardStore } from '@/store';

export const Dashboard: React.FC = () => {
  const navigate = useNavigate();
  const { metrics, activities, loading, refreshData, runDemo, runDemoAuto } = useDashboardStore();

  const [showTour, setShowTour] = useState(false);
  const [tourStep, setTourStep] = useState(0);

  useEffect(() => {
    // Auto-refresh every 30 seconds
    const interval = setInterval(() => {
      refreshData();
    }, 30000);

    return () => clearInterval(interval);
  }, [refreshData]);

  const getPipelineStatusDescription = () => {
    const descriptions = {
      idle: 'Workers are idle, waiting for opportunities',
      processing: 'Workers actively processing opportunities',
      degraded: 'System degraded, some workers offline',
      halted: 'Pipeline halted, immediate action required',
    } as const;
    return descriptions[metrics.pipelineState as keyof typeof descriptions];
  };

  const getRiskStatusDescription = () => {
    const descriptions = {
      green: 'System operating normally, all metrics green',
      elevated: 'Risk elevated, breakers may trigger soon',
      blocked: 'Risk breaker triggered, trading halted',
    } as const;
    return descriptions[metrics.riskStatus as keyof typeof descriptions];
  };

  const getExecutionHealthDescription = () => {
    const descriptions = {
      healthy: 'All executions completing successfully',
      warning: 'Some execution failures detected',
      critical: 'Critical execution failures, investigate immediately',
    } as const;
    return descriptions[metrics.executionHealth as keyof typeof descriptions];
  };

  const getSettlementStatusDescription = () => {
    const descriptions = {
      healthy: 'All settlements completing on schedule',
      warning: 'Some settlements delayed, monitoring',
      critical: 'Settlement failures, manual intervention needed',
    } as const;
    return descriptions[metrics.settlementStatus as keyof typeof descriptions];
  };

  const getPipelineHealthStatus = () => {
    if (metrics.pipelineState === 'halted') return 'critical';
    if (metrics.pipelineState === 'degraded') return 'warning';
    return 'healthy';
  };

  const getOpportunitiesHealthStatus = () => {
    if (metrics.totalOpportunities < 10) return 'warning';
    if (metrics.totalOpportunities > 300) return 'critical';
    return 'healthy';
  };

  const getMarketDataHealthStatus = () => {
    if (metrics.marketDataFreshness > 60) return 'critical';
    if (metrics.marketDataFreshness > 30) return 'warning';
    return 'healthy';
  };

  const actions = [
    {
      id: 'pipeline',
      label: 'View Pipeline',
      icon: Zap,
      path: '/pipeline',
    },
    {
      id: 'opportunities',
      label: 'View Opportunities',
      icon: Target,
      path: '/opportunities',
    },
    {
      id: 'risk',
      label: 'Open Risk Center',
      icon: AlertCircle,
      path: '/risk',
    },
    {
      id: 'execution',
      label: 'Open Execution',
      icon: Cpu,
      path: '/execution',
    },
    {
      id: 'settlement',
      label: 'Open Settlement',
      icon: CheckCircle,
      path: '/settlement',
    },
    {
      id: 'market',
      label: 'Open Market Data',
      icon: Database,
      path: '/market-data',
    },
    {
      id: 'compute',
      label: 'Open Compute',
      icon: Cpu,
      path: '/compute',
    },
  ];

  return (
    <Layout onRefresh={refreshData} isLoading={loading}>
      <div className="space-y-8">
        {/* Overview title */}
        <div>
          <h2 className="text-display-lg font-serif text-primary mb-2">System Overview</h2>
          <p className="text-body-md text-on-surface-variant">
            Monitor real-time metrics and take immediate action on any section
          </p>
        </div>

        {/* Top-level indicator strip - 6 core metrics */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-6 gap-4">
          <IndicatorCard
            title="Pipeline State"
            value={metrics.pipelineState.toUpperCase()}
            status={getPipelineHealthStatus()}
            statusLabel={metrics.pipelineState}
            description={getPipelineStatusDescription()}
            icon={Zap}
            onClick={() => navigate('/pipeline')}
            trend={{ value: metrics.totalOpportunities - 50, direction: 'up' }}
          />

          <IndicatorCard
            title="Total Opportunities"
            value={metrics.totalOpportunities}
            status={getOpportunitiesHealthStatus()}
            statusLabel={`${metrics.activeOpportunities} active`}
            description={`${metrics.activeOpportunities} actively processing`}
            icon={Target}
            onClick={() => navigate('/opportunities')}
            trend={{ value: 12, direction: 'up' }}
          />

          <IndicatorCard
            title="Risk Status"
            value={metrics.riskStatus.toUpperCase()}
            status={metrics.riskStatus === 'blocked' ? 'critical' : metrics.riskStatus === 'elevated' ? 'warning' : 'healthy'}
            statusLabel={`${metrics.openBreakers} breaker${metrics.openBreakers !== 1 ? 's' : ''}`}
            description={getRiskStatusDescription()}
            icon={AlertCircle}
            onClick={() => navigate('/risk')}
          />

          <IndicatorCard
            title="Execution Health"
            value={metrics.recentExecutions}
            status={metrics.executionHealth}
            statusLabel={`${metrics.recentExecutions} today`}
            description={getExecutionHealthDescription()}
            icon={Cpu}
            onClick={() => navigate('/execution')}
            trend={{ value: 8, direction: 'up' }}
          />

          <IndicatorCard
            title="Settlement Status"
            value={metrics.settlementStatus.toUpperCase()}
            status={metrics.settlementStatus}
            statusLabel="Active"
            description={getSettlementStatusDescription()}
            icon={CheckCircle}
            onClick={() => navigate('/settlement')}
          />

          <IndicatorCard
            title="Market Data Freshness"
            value={`${metrics.marketDataFreshness}s`}
            status={getMarketDataHealthStatus()}
            statusLabel="age"
            description={`Updated ${new Date(metrics.lastMarketDataSample).toLocaleTimeString()}`}
            icon={Database}
            onClick={() => navigate('/market-data')}
          />
        </div>

        {/* Primary action buttons */}
        <div className="bg-white rounded-lg p-6 border border-outline-variant/20 shadow-elevation-1">
          <h3 className="text-headline-sm font-serif mb-6 text-primary">Quick Navigation</h3>
          <div className="flex items-center justify-between">
            <ActionButtons actions={actions} />
            <div className="ml-4 flex items-center gap-2">
              <button className="btn-secondary" onClick={() => setShowTour(true)}>Guided Tour</button>
              <button className="btn-primary" onClick={() => { runDemo(); setShowTour(false); }}>Run Demo</button>
              <button className="btn-primary" onClick={async () => { await runDemoAuto(); setShowTour(false); }}>Run Full Demo</button>
            </div>
          </div>
        </div>

        {/* Recent activity section */}
        <ActivityFeed activities={activities} />

        {/* Additional metrics grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="card">
            <p className="text-label-md text-on-surface-variant mb-2">Active Opportunities</p>
            <p className="text-headline-md font-serif text-primary mb-1">{metrics.activeOpportunities}</p>
            <p className="text-label-sm text-on-surface-variant">Currently processing</p>
          </div>

          <div className="card">
            <p className="text-label-md text-on-surface-variant mb-2">Live Positions</p>
            <p className="text-headline-md font-serif text-primary mb-1">{metrics.livePositions}</p>
            <p className="text-label-sm text-on-surface-variant">Open trades</p>
          </div>

          <div className="card">
            <p className="text-label-md text-on-surface-variant mb-2">Open Breakers</p>
            <p className="text-headline-md font-serif text-primary mb-1">{metrics.openBreakers}</p>
            <p className="text-label-sm text-on-surface-variant">Risk controls</p>
          </div>

          <div className="card">
            <p className="text-label-md text-on-surface-variant mb-2">Recent Executions</p>
            <p className="text-headline-md font-serif text-primary mb-1">{metrics.recentExecutions}</p>
            <p className="text-label-sm text-on-surface-variant">In last 24h</p>
          </div>
        </div>
      </div>
      {/* Guided tour modal */}
      {showTour && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
          <div className="card w-[560px] p-6">
            <h3 className="text-headline-sm font-serif mb-3">Quick Demo Tour</h3>
            <div className="text-body-md mb-4">
              {tourStep === 0 && <p>Step 1: Open <strong>Opportunities</strong> and locate the seeded demo item <em>OPP-9999</em>.</p>}
              {tourStep === 1 && <p>Step 2: Click <strong>Simulate</strong> to run a pre-flight check, then <strong>Approve</strong> to send to execution.</p>}
              {tourStep === 2 && <p>Step 3: Visit <strong>Execution</strong> to broadcast the tx, then <strong>Settlement</strong> to review the realized PnL and ledger export.</p>}
            </div>
            <div className="flex justify-between">
              <div>
                <button className="btn-secondary mr-2" onClick={() => { if (tourStep > 0) setTourStep(tourStep - 1); else setShowTour(false); }}>
                  {tourStep > 0 ? 'Back' : 'Close'}
                </button>
              </div>
              <div className="flex items-center gap-2">
                <button className="btn-secondary" onClick={() => { runDemo(); setShowTour(false); }}>Skip and Run Demo</button>
                {tourStep < 2 ? (
                  <button className="btn-primary" onClick={() => setTourStep(tourStep + 1)}>Next</button>
                ) : (
                  <button className="btn-primary" onClick={() => { runDemo(); setShowTour(false); }}>Start Demo</button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </Layout>
  );
};

export default Dashboard;
