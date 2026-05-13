import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { Layout } from '@/components';
import { useDashboardStore } from '@/store';
import StatusBadge from '@/components/StatusBadge';

export const Risk: React.FC = () => {
  const navigate = useNavigate();
  const riskCenter = useDashboardStore((s) => s.riskCenter);
  const acknowledgeBreaker = useDashboardStore((s) => s.acknowledgeBreaker);
  const acknowledgeOverride = useDashboardStore((s) => s.acknowledgeOverride);
  const triggerEmergencyStop = useDashboardStore((s) => s.triggerEmergencyStop);
  const addActivity = useDashboardStore((s) => s.addActivity);

  const [emergencyPrompt, setEmergencyPrompt] = useState<{ open: boolean; reason: string }>({ open: false, reason: '' });

  const overallStatusColor = {
    green: 'bg-green-100 text-green-900',
    elevated: 'bg-yellow-100 text-yellow-900',
    blocked: 'bg-red-100 text-red-900',
    emergency: 'bg-red-200 text-red-900',
  };

  const breakerStatusColor = {
    healthy: 'bg-green-100 text-green-900',
    warning: 'bg-yellow-100 text-yellow-900',
    triggered: 'bg-red-100 text-red-900',
  };

  const positionStateColor = {
    active: 'text-green-600',
    at_risk: 'text-yellow-600',
    critical: 'text-red-600',
  };

  const handleEmergencyStop = () => {
    triggerEmergencyStop(emergencyPrompt.reason, 'operator@flashix.com');
    addActivity({
      id: `emergency-${Date.now()}`,
      type: 'risk_event',
      timestamp: new Date(),
      title: 'Emergency Stop Triggered',
      description: emergencyPrompt.reason,
      status: 'critical',
    });
    setEmergencyPrompt({ open: false, reason: '' });
  };

  const activeEmergency = riskCenter.overrides.some((o) => o.active && o.pausesTrading);

  return (
    <Layout>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate('/')}
              className="p-2 hover:bg-surface-container rounded-lg transition-colors"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div>
              <h1 className="text-display-lg font-serif text-primary">Risk Center</h1>
              <p className="text-body-md text-on-surface-variant">Safety, exposure, and control management</p>
            </div>
          </div>
          <div className={`px-4 py-2 rounded-lg text-label-md font-semibold ${overallStatusColor[riskCenter.overallStatus]}`}>
            {riskCenter.overallStatus.toUpperCase()}
          </div>
        </div>

        {/* Circuit Breakers Section */}
        <div className="space-y-3">
          <h2 className="text-headline-sm font-serif">Circuit Breakers</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {riskCenter.breakers.map((breaker) => (
              <div key={breaker.id} className={`card border-2 ${breakerStatusColor[breaker.status]}`}>
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <p className="text-label-md text-on-surface-variant uppercase tracking-wider">{breaker.name}</p>
                    <h3 className="text-headline-sm font-serif mt-1">{breaker.trigger}</h3>
                  </div>
                  <StatusBadge status={breaker.status === 'triggered' ? 'critical' : breaker.status === 'warning' ? 'warning' : 'healthy'} label={breaker.status} />
                </div>

                <div className="grid grid-cols-2 gap-3 mb-3">
                  <div>
                    <p className="text-label-sm text-on-surface-variant">Threshold</p>
                    <p className="text-body-md">${breaker.threshold.toLocaleString()}</p>
                  </div>
                  <div>
                    <p className="text-label-sm text-on-surface-variant">Current</p>
                    <p className="text-body-md">${breaker.current.toLocaleString()}</p>
                  </div>
                </div>

                {breaker.activatedAt && (
                  <div className="mb-3">
                    <p className="text-label-sm text-on-surface-variant">Activated</p>
                    <p className="text-body-md">{new Date(breaker.activatedAt).toLocaleString()}</p>
                  </div>
                )}

                {breaker.affectedTradeCount !== undefined && (
                  <div className="mb-3">
                    <p className="text-label-sm text-on-surface-variant">Affected trades</p>
                    <p className="text-body-md">{breaker.affectedTradeCount}</p>
                  </div>
                )}

                <div className="flex gap-2">
                  <button className="btn-secondary text-sm">
                    Details
                  </button>
                  <button className="btn-secondary text-sm">
                    Affected
                  </button>
                  {breaker.status !== 'healthy' && (
                    <button className="btn-primary text-sm" onClick={() => acknowledgeBreaker(breaker.id)}>
                      Acknowledge
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Portfolio Limits Section */}
        <div className="card">
          <h2 className="text-headline-sm font-serif mb-4">Portfolio Limits</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div>
              <p className="text-label-sm text-on-surface-variant">Daily Loss Limit</p>
              <p className="text-headline-sm font-serif">${riskCenter.limits.dailyLossLimit.toLocaleString()}</p>
              <p className="text-label-sm text-on-surface-variant mt-1">Current: ${riskCenter.limits.currentDailyLoss.toLocaleString()}</p>
              <div className="mt-2 w-full bg-surface-container rounded-full h-2">
                <div
                  className={`h-2 rounded-full ${riskCenter.limits.currentDailyLoss / riskCenter.limits.dailyLossLimit > 0.8 ? 'bg-red-500' : 'bg-yellow-500'}`}
                  style={{ width: `${Math.min(100, (riskCenter.limits.currentDailyLoss / riskCenter.limits.dailyLossLimit) * 100)}%` }}
                />
              </div>
            </div>

            <div>
              <p className="text-label-sm text-on-surface-variant">Collateral Ratio</p>
              <p className="text-headline-sm font-serif">{riskCenter.limits.collateralRatio.toFixed(1)}x</p>
              <p className="text-label-sm text-on-surface-variant mt-1">Limit: {riskCenter.limits.collateralLimit.toFixed(1)}x</p>
              <div className="mt-2 w-full bg-surface-container rounded-full h-2">
                <div
                  className={`h-2 rounded-full ${riskCenter.limits.collateralRatio < riskCenter.limits.collateralLimit * 0.8 ? 'bg-red-500' : 'bg-green-500'}`}
                  style={{ width: `${Math.min(100, (riskCenter.limits.collateralRatio / riskCenter.limits.collateralLimit) * 100)}%` }}
                />
              </div>
            </div>

            <div>
              <p className="text-label-sm text-on-surface-variant">Open Positions</p>
              <p className="text-headline-sm font-serif">{riskCenter.limits.currentPositions}/{riskCenter.limits.maxConcurrentPositions}</p>
              <p className="text-label-sm text-on-surface-variant mt-1">Max: {riskCenter.limits.maxConcurrentPositions}</p>
              <div className="mt-2 w-full bg-surface-container rounded-full h-2">
                <div
                  className={`h-2 rounded-full ${riskCenter.limits.currentPositions > riskCenter.limits.maxConcurrentPositions * 0.8 ? 'bg-yellow-500' : 'bg-green-500'}`}
                  style={{ width: `${Math.min(100, (riskCenter.limits.currentPositions / riskCenter.limits.maxConcurrentPositions) * 100)}%` }}
                />
              </div>
            </div>

            <div>
              <p className="text-label-sm text-on-surface-variant">Slippage Limit</p>
              <p className="text-headline-sm font-serif">{riskCenter.limits.currentSlippagePct.toFixed(2)}%</p>
              <p className="text-label-sm text-on-surface-variant mt-1">Max: {riskCenter.limits.slippageLimitPct}%</p>
              <div className="mt-2 w-full bg-surface-container rounded-full h-2">
                <div
                  className={`h-2 rounded-full ${riskCenter.limits.currentSlippagePct > riskCenter.limits.slippageLimitPct * 0.8 ? 'bg-red-500' : 'bg-green-500'}`}
                  style={{ width: `${Math.min(100, (riskCenter.limits.currentSlippagePct / riskCenter.limits.slippageLimitPct) * 100)}%` }}
                />
              </div>
            </div>
          </div>
        </div>

        {/* Open Positions Section */}
        <div className="card">
          <h2 className="text-headline-sm font-serif mb-4">Live Positions</h2>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-outline-variant/30">
                  <th className="text-left py-3 px-4 text-label-md text-on-surface-variant">Trade</th>
                  <th className="text-right py-3 px-4 text-label-md text-on-surface-variant">Exposure</th>
                  <th className="text-left py-3 px-4 text-label-md text-on-surface-variant">Entry Time</th>
                  <th className="text-left py-3 px-4 text-label-md text-on-surface-variant">State</th>
                  <th className="text-left py-3 px-4 text-label-md text-on-surface-variant">Risk Impact</th>
                </tr>
              </thead>
              <tbody>
                {riskCenter.positions.map((pos) => (
                  <tr key={pos.id} className="border-b border-outline-variant/20 hover:bg-surface-container transition-colors">
                    <td className="py-4 px-4 text-body-md">{pos.tradeName}</td>
                    <td className="py-4 px-4 text-right text-body-md">${pos.exposureSize.toLocaleString()}</td>
                    <td className="py-4 px-4 text-label-sm text-on-surface-variant">{new Date(pos.entryTime).toLocaleString()}</td>
                    <td className={`py-4 px-4 text-body-md font-semibold ${positionStateColor[pos.currentState]}`}>
                      {pos.currentState.replace('_', ' ').toUpperCase()}
                    </td>
                    <td className="py-4 px-4">
                      {pos.affectsBreakerIds && pos.affectsBreakerIds.length > 0 && (
                        <span className="text-label-sm text-red-600">Breaker impact</span>
                      )}
                      {(!pos.affectsBreakerIds || pos.affectsBreakerIds.length === 0) && (
                        <span className="text-label-sm text-green-600">No breaker impact</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Human Override Controls Section */}
        <div className="card bg-red-50 border-2 border-red-200">
          <h2 className="text-headline-sm font-serif mb-4">Human Override Controls</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div>
              <p className="text-label-sm text-on-surface-variant">Last Override</p>
              {riskCenter.overrides.length > 0 ? (
                <div className="mt-2">
                  <p className="text-body-md">{riskCenter.overrides[riskCenter.overrides.length - 1].triggeredBy}</p>
                  <p className="text-label-sm text-on-surface-variant">{new Date(riskCenter.overrides[riskCenter.overrides.length - 1].triggeredAt).toLocaleString()}</p>
                  <p className="text-label-sm text-on-surface-variant mt-1">{riskCenter.overrides[riskCenter.overrides.length - 1].reason}</p>
                </div>
              ) : (
                <p className="text-body-md">No overrides</p>
              )}
            </div>

            <div>
              <p className="text-label-sm text-on-surface-variant">Active Overrides</p>
              <div className="mt-2 space-y-2">
                {riskCenter.overrides.filter((o) => o.active).map((o) => (
                  <div key={o.id} className="p-3 bg-white rounded border border-red-300">
                    <p className="text-label-md font-semibold text-red-900">{o.reason}</p>
                    <p className="text-label-sm text-red-700 mt-1">By {o.triggeredBy}</p>
                    <button className="btn-secondary text-sm mt-2" onClick={() => acknowledgeOverride(o.id)}>
                      Clear Override
                    </button>
                  </div>
                ))}
                {riskCenter.overrides.filter((o) => o.active).length === 0 && (
                  <p className="text-label-sm text-green-600">No active overrides</p>
                )}
              </div>
            </div>
          </div>

          <div className="pt-4 border-t border-red-200">
            <p className="text-label-sm text-on-surface-variant mb-3">Emergency Action</p>
            <button
              className="px-6 py-3 bg-red-600 hover:bg-red-700 text-white rounded-lg font-semibold transition-colors"
              onClick={() => setEmergencyPrompt({ ...emergencyPrompt, open: true })}
              disabled={activeEmergency}
            >
              {activeEmergency ? 'Emergency Stop Active' : 'Trigger Emergency Stop'}
            </button>
          </div>
        </div>

        {/* Emergency Stop Prompt */}
        {emergencyPrompt.open && (
          <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
            <div className="card w-[520px] border-2 border-red-500">
              <h3 className="text-headline-sm font-serif text-red-900 mb-2">Confirm Emergency Stop</h3>
              <p className="text-body-md text-on-surface-variant mb-3">This will immediately pause all trading. Provide a reason:</p>
              <textarea
                className="w-full p-3 border border-red-300 rounded"
                rows={4}
                value={emergencyPrompt.reason}
                onChange={(e) => setEmergencyPrompt({ ...emergencyPrompt, reason: e.target.value })}
                placeholder="Reason for emergency stop"
              />
              <div className="mt-4 flex justify-end gap-2">
                <button className="btn-secondary" onClick={() => setEmergencyPrompt({ open: false, reason: '' })}>
                  Cancel
                </button>
                <button className="px-6 py-3 bg-red-600 hover:bg-red-700 text-white rounded font-semibold" onClick={handleEmergencyStop}>
                  Confirm Emergency Stop
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </Layout>
  );
};

export default Risk;
