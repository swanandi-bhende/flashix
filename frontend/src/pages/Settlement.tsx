import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, TrendingUp, Lock, Unlock, FileText, BarChart3 } from 'lucide-react';
import { Layout } from '@/components';
import { useDashboardStore } from '@/store';
import StatusBadge from '@/components/StatusBadge';

export const Settlement: React.FC = () => {
  const navigate = useNavigate();
  const settlement = useDashboardStore((s) => s.settlementCenter);
  const closePosition = useDashboardStore((s) => s.closePosition);
  const recordRepayment = useDashboardStore((s) => s.recordRepayment);
  const generateLedgerExport = useDashboardStore((s) => s.generateLedgerExport);
  const compareExpectedVsRealized = useDashboardStore((s) => s.compareExpectedVsRealized);
  const addActivity = useDashboardStore((s) => s.addActivity);

  const [expandedLedgerId, setExpandedLedgerId] = useState<string | null>(null);
  const [selectedPosition, setSelectedPosition] = useState<string | null>(null);
  const [exportingTime, setExportingTime] = useState<{ start: string; end: string } | null>(null);

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
      case 'healthy':
        return 'bg-green-50 border-green-300';
      case 'partially_repaid':
      case 'at_risk':
        return 'bg-yellow-50 border-yellow-300';
      case 'pending':
        return 'bg-blue-50 border-blue-300';
      case 'overdue':
      case 'critical':
        return 'bg-red-50 border-red-300';
      default:
        return 'bg-gray-50 border-gray-300';
    }
  };

  const handleClosePosition = (positionId: string) => {
    closePosition(positionId);
    addActivity({
      id: `close-${Date.now()}`,
      type: 'settlement',
      timestamp: new Date(),
      title: 'Position close initiated',
      description: `Position ${positionId} is being liquidated`,
      status: 'warning',
    });
    setSelectedPosition(null);
  };

  const handleRecordRepayment = (repaymentId: string, amount: number) => {
    recordRepayment(repaymentId, amount);
    addActivity({
      id: `repay-${Date.now()}`,
      type: 'settlement',
      timestamp: new Date(),
      title: 'Repayment recorded',
      description: `$${amount.toLocaleString()} recorded for ${repaymentId}`,
      status: 'healthy',
    });
  };

  const handleGenerateExport = () => {
    if (exportingTime) {
      generateLedgerExport({
        start: new Date(exportingTime.start),
        end: new Date(exportingTime.end),
      });
      setExportingTime(null);
    }
  };

  const handleCompareExpectedVsRealized = (tradeId: string) => {
    compareExpectedVsRealized(tradeId);
    addActivity({
      id: `compare-${Date.now()}`,
      type: 'settlement',
      timestamp: new Date(),
      title: 'Performance analysis initiated',
      description: `Expected vs realized analysis for ${tradeId}`,
      status: 'healthy',
    });
  };

  const getPnLColor = (value: number) => value >= 0 ? 'text-green-600' : 'text-red-600';

  return (
    <Layout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate('/')}
              className="p-2 hover:bg-surface-container rounded-lg transition-colors"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div>
              <h1 className="text-display-lg font-serif text-primary">Settlement & Portfolio</h1>
              <p className="text-body-md text-on-surface-variant">Post-trade outcomes, positions, and accounting</p>
            </div>
          </div>
          <div className={`px-4 py-2 rounded-lg text-label-md font-semibold ${settlement.overallStatus === 'healthy' ? 'bg-green-100 text-green-900' : settlement.overallStatus === 'at_risk' ? 'bg-yellow-100 text-yellow-900' : 'bg-red-100 text-red-900'}`}>
            {settlement.overallStatus.toUpperCase()}
          </div>
        </div>

        {/* 4-Question Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="card border-2 border-green-300">
            <p className="text-label-md text-on-surface-variant mb-2">❶ What did we earn?</p>
            <p className={`text-display-sm font-serif ${getPnLColor(settlement.totalRealizedPnL)}`}>
              ${settlement.totalRealizedPnL.toLocaleString()}
            </p>
            <p className="text-label-sm text-on-surface-variant mt-1">{settlement.realizedPnLList.length} trades realized</p>
          </div>

          <div className="card border-2 border-blue-300">
            <p className="text-label-md text-on-surface-variant mb-2">❷ What is still open?</p>
            <p className="text-display-sm font-serif text-primary">{settlement.openPositions.length}</p>
            <p className="text-label-sm text-on-surface-variant mt-1">${settlement.totalUnrealizedPnL > 0 ? '+' : ''}${settlement.totalUnrealizedPnL.toLocaleString()} unrealized</p>
          </div>

          <div className="card border-2 border-yellow-300">
            <p className="text-label-md text-on-surface-variant mb-2">❸ What still needs repayment?</p>
            <p className="text-display-sm font-serif text-primary">
              {settlement.repaymentStatuses.filter((r) => ['pending', 'partially_repaid'].includes(r.status)).length}
            </p>
            <p className="text-label-sm text-on-surface-variant mt-1">Outstanding obligations</p>
          </div>

          <div className="card border-2 border-purple-300">
            <p className="text-label-md text-on-surface-variant mb-2">❹ Portfolio balance</p>
            <p className="text-display-sm font-serif text-primary">${settlement.portfolioBalance.toLocaleString()}</p>
            <p className="text-label-sm text-on-surface-variant mt-1">Mark + Unrealized</p>
          </div>
        </div>

        {/* Realized PnL Section */}
        <div className="card border-2 border-green-300">
          <div className="flex items-center gap-2 mb-4">
            <TrendingUp className="w-5 h-5 text-green-600" />
            <h2 className="text-headline-sm font-serif">Realized PnL</h2>
            <span className="text-label-sm text-on-surface-variant">Trading results by trade and session</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-6">
            <div className="p-4 bg-green-50 rounded-lg border border-green-200">
              <p className="text-label-md text-on-surface-variant">Total Realized</p>
              <p className={`text-headline-md font-serif mt-1 ${getPnLColor(settlement.totalRealizedPnL)}`}>
                ${settlement.totalRealizedPnL.toLocaleString()}
              </p>
            </div>
            <div className="p-4 bg-blue-50 rounded-lg border border-blue-200">
              <p className="text-label-md text-on-surface-variant">Total Unrealized</p>
              <p className={`text-headline-md font-serif mt-1 ${getPnLColor(settlement.totalUnrealizedPnL)}`}>
                ${settlement.totalUnrealizedPnL.toLocaleString()}
              </p>
            </div>
            <div className="p-4 bg-purple-50 rounded-lg border border-purple-200">
              <p className="text-label-md text-on-surface-variant">Accounting Balance</p>
              <p className="text-headline-md font-serif mt-1 text-primary">
                ${settlement.accountingBalance.toLocaleString()}
              </p>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-outline-variant/30">
                  <th className="text-left py-3 px-4 text-label-md text-on-surface-variant">Trade ID</th>
                  <th className="text-left py-3 px-4 text-label-md text-on-surface-variant">Symbol</th>
                  <th className="text-right py-3 px-4 text-label-md text-on-surface-variant">Planned</th>
                  <th className="text-right py-3 px-4 text-label-md text-on-surface-variant">Gas Cost</th>
                  <th className="text-right py-3 px-4 text-label-md text-on-surface-variant">Realized</th>
                  <th className="text-center py-3 px-4 text-label-md text-on-surface-variant">Status</th>
                  <th className="text-center py-3 px-4 text-label-md text-on-surface-variant">Action</th>
                </tr>
              </thead>
              <tbody>
                {settlement.realizedPnLList.map((pnl) => (
                  <tr key={pnl.tradeId} className="border-b border-outline-variant/20 hover:bg-surface-container transition-colors">
                    <td className="py-4 px-4 text-body-md font-mono text-primary">{pnl.tradeId}</td>
                    <td className="py-4 px-4 text-body-md">{pnl.symbol}</td>
                    <td className="py-4 px-4 text-right text-label-md">${pnl.plannedProfit.toLocaleString()}</td>
                    <td className="py-4 px-4 text-right text-label-md text-red-600">-${pnl.actualGasCost}</td>
                    <td className={`py-4 px-4 text-right text-label-md font-semibold ${getPnLColor(pnl.actualProfit)}`}>
                      ${pnl.actualProfit.toLocaleString()}
                    </td>
                    <td className="py-4 px-4 text-center">
                      <StatusBadge status={pnl.status === 'completed' ? 'healthy' : 'warning'} label={pnl.status} />
                    </td>
                    <td className="py-4 px-4 text-center">
                      <button
                        onClick={() => handleCompareExpectedVsRealized(pnl.tradeId)}
                        className="text-sm px-3 py-1 bg-blue-100 text-blue-700 hover:bg-blue-200 rounded transition-colors"
                      >
                        Compare
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Open Positions Section */}
        <div className="card border-2 border-blue-300">
          <div className="flex items-center gap-2 mb-4">
            <Lock className="w-5 h-5 text-blue-600" />
            <h2 className="text-headline-sm font-serif">Open Positions</h2>
            <span className="text-label-sm text-on-surface-variant">Live portfolio exposure</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-outline-variant/30">
                  <th className="text-left py-3 px-4 text-label-md text-on-surface-variant">Symbol</th>
                  <th className="text-right py-3 px-4 text-label-md text-on-surface-variant">Size</th>
                  <th className="text-right py-3 px-4 text-label-md text-on-surface-variant">Entry Price</th>
                  <th className="text-right py-3 px-4 text-label-md text-on-surface-variant">Mark</th>
                  <th className="text-right py-3 px-4 text-label-md text-on-surface-variant">Exposure</th>
                  <th className="text-right py-3 px-4 text-label-md text-on-surface-variant">Unrealized PnL</th>
                  <th className="text-center py-3 px-4 text-label-md text-on-surface-variant">Status</th>
                  <th className="text-center py-3 px-4 text-label-md text-on-surface-variant">Action</th>
                </tr>
              </thead>
              <tbody>
                {settlement.openPositions.map((pos) => (
                  <tr key={pos.id} className="border-b border-outline-variant/20 hover:bg-surface-container transition-colors">
                    <td className="py-4 px-4 text-body-md font-semibold">{pos.symbol}</td>
                    <td className="py-4 px-4 text-right text-body-md">{pos.size}</td>
                    <td className="py-4 px-4 text-right text-label-md">${pos.entryPrice.toLocaleString()}</td>
                    <td className="py-4 px-4 text-right text-label-md font-semibold text-primary">${pos.currentMark.toLocaleString()}</td>
                    <td className="py-4 px-4 text-right text-label-md">${pos.exposure.toLocaleString()}</td>
                    <td className={`py-4 px-4 text-right text-label-md font-semibold ${getPnLColor(pos.unrealizedPnL)}`}>
                      ${pos.unrealizedPnL.toLocaleString()}
                    </td>
                    <td className="py-4 px-4 text-center">
                      <StatusBadge
                        status={pos.status === 'active' ? 'healthy' : pos.status === 'at_risk' ? 'warning' : 'critical'}
                        label={pos.status}
                      />
                    </td>
                    <td className="py-4 px-4 text-center">
                      <button
                        onClick={() => setSelectedPosition(pos.id)}
                        disabled={pos.status === 'liquidating'}
                        className="text-sm px-3 py-1 bg-red-100 text-red-700 hover:bg-red-200 rounded transition-colors disabled:opacity-50"
                      >
                        Close
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Repayment Status Section */}
        <div className="card border-2 border-yellow-300">
          <div className="flex items-center gap-2 mb-4">
            <Unlock className="w-5 h-5 text-yellow-600" />
            <h2 className="text-headline-sm font-serif">Repayment Status</h2>
            <span className="text-label-sm text-on-surface-variant">Outstanding obligations and settlements</span>
          </div>

          <div className="space-y-4">
            {settlement.repaymentStatuses.map((rep) => (
              <div key={rep.id} className={`card border-2 p-4 ${getStatusColor(rep.status)}`}>
                <div className="flex justify-between items-start mb-3">
                  <div>
                    <p className="text-label-md font-semibold text-on-surface">{rep.obligationType.replace('_', ' ').toUpperCase()}</p>
                    <p className="text-body-md mt-1">${rep.amount.toLocaleString()}</p>
                  </div>
                  <StatusBadge status={rep.status === 'completed' ? 'healthy' : rep.status === 'overdue' ? 'critical' : 'warning'} label={rep.status} />
                </div>

                <div className="grid grid-cols-2 gap-4 mb-3">
                  <div>
                    <p className="text-label-sm text-on-surface-variant">Borrowed at</p>
                    <p className="text-label-md mt-1">{new Date(rep.borrowedAt).toLocaleString()}</p>
                  </div>
                  {rep.dueDate && (
                    <div>
                      <p className="text-label-sm text-on-surface-variant">Due</p>
                      <p className="text-label-md mt-1">{new Date(rep.dueDate).toLocaleString()}</p>
                    </div>
                  )}
                </div>

                <div className="mb-3">
                  <div className="flex justify-between mb-2">
                    <p className="text-label-sm text-on-surface-variant">Repaid</p>
                    <p className="text-label-sm font-semibold">${rep.repaidAmount.toLocaleString()} / ${rep.amount.toLocaleString()}</p>
                  </div>
                  <div className="w-full bg-surface-container rounded-full h-2">
                    <div
                      className={`h-2 rounded-full ${rep.status === 'completed' ? 'bg-green-500' : 'bg-yellow-500'}`}
                      style={{ width: `${Math.min(100, (rep.repaidAmount / rep.amount) * 100)}%` }}
                    />
                  </div>
                </div>

                {rep.status !== 'completed' && (
                  <button
                    onClick={() => handleRecordRepayment(rep.id, rep.amount - rep.repaidAmount)}
                    className="w-full text-sm px-3 py-2 bg-green-100 text-green-700 hover:bg-green-200 rounded transition-colors"
                  >
                    Record Repayment
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Ledger Entries Section */}
        <div className="card border-2 border-purple-300">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <FileText className="w-5 h-5 text-purple-600" />
              <h2 className="text-headline-sm font-serif">Ledger Entries</h2>
              <span className="text-label-sm text-on-surface-variant">Accounting records</span>
            </div>
            <button onClick={() => setExportingTime({ start: new Date(Date.now() - 86400000).toISOString(), end: new Date().toISOString() })} className="text-sm px-3 py-2 bg-purple-100 text-purple-700 hover:bg-purple-200 rounded transition-colors">
              <BarChart3 className="w-4 h-4 inline mr-1" />
              Export Report
            </button>
          </div>

          {exportingTime && (
            <div className="mb-4 p-4 bg-purple-50 border border-purple-200 rounded-lg">
              <p className="text-label-md font-semibold mb-2">Export Ledger Report</p>
              <div className="grid grid-cols-2 gap-3 mb-3">
                <input
                  type="datetime-local"
                  value={exportingTime.start}
                  onChange={(e) => setExportingTime({ ...exportingTime, start: e.target.value })}
                  className="px-3 py-2 border border-outline-variant rounded text-sm"
                  placeholder="Start date"
                />
                <input
                  type="datetime-local"
                  value={exportingTime.end}
                  onChange={(e) => setExportingTime({ ...exportingTime, end: e.target.value })}
                  className="px-3 py-2 border border-outline-variant rounded text-sm"
                  placeholder="End date"
                />
              </div>
              <div className="flex gap-2">
                <button onClick={handleGenerateExport} className="px-3 py-2 bg-green-600 hover:bg-green-700 text-white rounded text-sm font-semibold">
                  Generate & Download
                </button>
                <button onClick={() => setExportingTime(null)} className="px-3 py-2 bg-gray-300 hover:bg-gray-400 text-gray-800 rounded text-sm">
                  Cancel
                </button>
              </div>
            </div>
          )}

          <div className="space-y-2">
            {settlement.ledgerEntries.map((entry) => (
              <div
                key={entry.id}
                className="border border-outline-variant/30 rounded-lg p-4 hover:bg-surface-container transition-colors cursor-pointer"
                onClick={() => setExpandedLedgerId(expandedLedgerId === entry.id ? null : entry.id)}
              >
                <div className="flex justify-between items-center">
                  <div className="flex-1">
                    <p className="text-label-md font-semibold">{entry.entryType.replace('_', ' ').toUpperCase()}</p>
                    <p className="text-label-sm text-on-surface-variant mt-1">{entry.description}</p>
                  </div>
                  <div className="text-right ml-4">
                    <p className={`text-body-md font-semibold ${getPnLColor(entry.amount)}`}>${entry.amount.toLocaleString()}</p>
                    <p className="text-label-sm text-on-surface-variant">{new Date(entry.timestamp).toLocaleString()}</p>
                  </div>
                </div>

                {expandedLedgerId === entry.id && (
                  <div className="mt-4 pt-4 border-t border-outline-variant/30">
                    <div className="grid grid-cols-2 gap-4 mb-4">
                      <div>
                        <p className="text-label-sm text-on-surface-variant">Trade ID</p>
                        <p className="text-label-md font-mono mt-1">{entry.tradeId}</p>
                      </div>
                      <div>
                        <p className="text-label-sm text-on-surface-variant">Balance After</p>
                        <p className="text-label-md font-semibold mt-1">${entry.balanceAfter.toLocaleString()}</p>
                      </div>
                    </div>
                    {entry.linkedSettlement && (
                      <div>
                        <p className="text-label-sm text-on-surface-variant">Linked Settlement</p>
                        <p className="text-label-md font-mono mt-1">{entry.linkedSettlement}</p>
                      </div>
                    )}
                    <button className="mt-4 text-sm px-3 py-2 bg-blue-100 text-blue-700 hover:bg-blue-200 rounded transition-colors">
                      View Ledger Entry
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Close Position Modal */}
        {selectedPosition && (
          <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
            <div className="card w-[480px] border-2 border-red-500">
              <h3 className="text-headline-sm font-serif text-red-900 mb-3">Confirm Position Close</h3>
              <p className="text-body-md text-on-surface-variant mb-4">
                This will initiate liquidation of position {selectedPosition}. This action cannot be undone immediately.
              </p>
              <div className="flex gap-2 justify-end">
                <button onClick={() => setSelectedPosition(null)} className="btn-secondary">
                  Cancel
                </button>
                <button onClick={() => handleClosePosition(selectedPosition)} className="px-6 py-3 bg-red-600 hover:bg-red-700 text-white rounded font-semibold">
                  Close Position
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </Layout>
  );
};

export default Settlement;
