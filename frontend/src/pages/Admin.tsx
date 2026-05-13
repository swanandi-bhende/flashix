import React, { useState, useMemo } from 'react';
import { useDashboardStore } from '@/store';
import StatusBadge from '@/components/StatusBadge';
import Layout from '@/components/Layout';
import {
  Settings,
  CheckCircle,
  AlertTriangle,
  Edit2,
  Download,
  Search,
  Filter,
  Save,
  Zap,
  Clock,
  ChevronDown,
  ChevronUp,
  X,
} from 'lucide-react';
import type { AuditActionType } from '@/types';

export default function Admin() {
  const { adminCenter, editProvider, updateContract, saveConfig, downloadReplayReport, filterAuditByType } = useDashboardStore();
  
  const [expandedProvider, setExpandedProvider] = useState<string | null>(null);
  const [selectedAuditAction, setSelectedAuditAction] = useState<AuditActionType | null>(null);
  const [auditSearchSubsystem, setAuditSearchSubsystem] = useState<string>('');
  const [showSaveConfirmation, setShowSaveConfirmation] = useState(false);
  const [showDetailView, setShowDetailView] = useState<{ type: 'provider' | 'contract' | 'change' | 'audit'; id: string } | null>(null);

  // Filter audit log based on selections
  const filteredAudit = useMemo(() => {
    let results = adminCenter.auditLog;
    
    if (selectedAuditAction) {
      results = filterAuditByType(selectedAuditAction);
    }
    
    if (auditSearchSubsystem) {
      results = results.filter((entry) => entry.subsystem === auditSearchSubsystem);
    }
    
    return results.sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime());
  }, [adminCenter.auditLog, selectedAuditAction, auditSearchSubsystem, filterAuditByType]);

  const allActionTypes: AuditActionType[] = ['config_change', 'contract_update', 'operator_action', 'trade_decision', 'security_event'];
  const allSubsystems = Array.from(new Set(adminCenter.auditLog.map((e) => e.subsystem)));

  return (
    <Layout>
      <div className="space-y-8">
        {/* Header */}
        <div className="border-b border-gray-200 pb-6">
          <h1 className="text-3xl font-serif font-bold text-gray-900 mb-2">Admin & Settings</h1>
          <p className="text-gray-600">Backend control plane for configuration, deployment, and historical review</p>
        </div>

        {/* Three Key Questions Summary */}
        <div className="grid grid-cols-3 gap-4">
          <div className="border border-gray-200 rounded-lg p-4 bg-blue-50">
            <div className="flex items-center gap-2 mb-2">
              <Settings className="w-5 h-5 text-blue-700" />
              <h3 className="font-semibold text-gray-900">What Can Be Configured?</h3>
            </div>
            <p className="text-sm text-gray-600 mb-2">Providers, contracts, and system settings</p>
            <p className="text-lg font-bold text-blue-700">{adminCenter.providers.length}</p>
            <p className="text-xs text-gray-500">External providers configured</p>
          </div>

          <div className="border border-gray-200 rounded-lg p-4 bg-green-50">
            <div className="flex items-center gap-2 mb-2">
              <Zap className="w-5 h-5 text-green-700" />
              <h3 className="font-semibold text-gray-900">What Is Currently Deployed?</h3>
            </div>
            <p className="text-sm text-gray-600 mb-2">Active contracts and live configurations</p>
            <p className="text-lg font-bold text-green-700">{adminCenter.contracts.filter((c) => c.isActive).length}/{adminCenter.contracts.length}</p>
            <p className="text-xs text-gray-500">Contracts active and verified</p>
          </div>

          <div className="border border-gray-200 rounded-lg p-4 bg-purple-50">
            <div className="flex items-center gap-2 mb-2">
              <Clock className="w-5 h-5 text-purple-700" />
              <h3 className="font-semibold text-gray-900">What Happened in the Past?</h3>
            </div>
            <p className="text-sm text-gray-600 mb-2">Configuration changes and historical events</p>
            <p className="text-lg font-bold text-purple-700">{adminCenter.auditLog.length}</p>
            <p className="text-xs text-gray-500">Total audit log entries</p>
          </div>
        </div>

        {/* Edit Providers Section */}
        <div className="border border-gray-200 rounded-lg overflow-hidden">
          <div className="bg-gray-50 px-6 py-4 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900">Edit Providers</h2>
            <p className="text-sm text-gray-600 mt-1">Every external dependency the system relies on</p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-100 border-b border-gray-200">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-gray-700">Provider Name</th>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-gray-700">Type</th>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-gray-700">Endpoint</th>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-gray-700">Status</th>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-gray-700">Latency</th>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-gray-700">Actions</th>
                </tr>
              </thead>
              <tbody>
                {adminCenter.providers.map((provider) => (
                  <React.Fragment key={provider.id}>
                    <tr className="border-b border-gray-200 hover:bg-gray-50">
                      <td className="px-6 py-4 text-sm font-semibold text-gray-900">{provider.name}</td>
                      <td className="px-6 py-4 text-sm">
                        <span className="inline-block bg-blue-100 text-blue-700 px-2 py-1 rounded text-xs font-medium">{provider.type}</span>
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-600 font-mono text-xs truncate max-w-xs">{provider.endpoint}</td>
                      <td className="px-6 py-4 text-sm">
                        <StatusBadge
                          status={provider.isHealthy ? 'healthy' : provider.status === 'degraded' ? 'warning' : 'critical'}
                          label={provider.status}
                        />
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-700">{provider.averageLatencyMs}ms</td>
                      <td className="px-6 py-4 text-sm space-x-2">
                        <button
                          onClick={() => {
                            editProvider(provider.id);
                            setShowDetailView({ type: 'provider', id: provider.id });
                          }}
                          className="inline-flex items-center text-blue-600 hover:text-blue-700 font-medium gap-1"
                        >
                          <Edit2 className="w-4 h-4" />
                          Edit
                        </button>
                        <button
                          onClick={() => setExpandedProvider(expandedProvider === provider.id ? null : provider.id)}
                          className="inline-flex items-center text-gray-600 hover:text-gray-700"
                        >
                          {expandedProvider === provider.id ? (
                            <ChevronUp className="w-4 h-4" />
                          ) : (
                            <ChevronDown className="w-4 h-4" />
                          )}
                        </button>
                      </td>
                    </tr>
                    {expandedProvider === provider.id && (
                      <tr className="bg-blue-50 border-b border-gray-200">
                        <td colSpan={6} className="px-6 py-4">
                          <div className="space-y-2">
                            <div className="grid grid-cols-2 gap-4">
                              <div>
                                <p className="text-xs font-semibold text-gray-700 mb-1">Last Health Check</p>
                                <p className="text-sm text-gray-600">{provider.lastHealthCheck.toLocaleString()}</p>
                              </div>
                              <div>
                                <p className="text-xs font-semibold text-gray-700 mb-1">Failure Count</p>
                                <p className="text-sm text-gray-600">{provider.failureCount}</p>
                              </div>
                            </div>
                            <div>
                              <p className="text-xs font-semibold text-gray-700 mb-1">Configuration Details</p>
                              <pre className="bg-white p-2 rounded border border-gray-200 text-xs overflow-auto max-h-20">
                                {JSON.stringify(provider.details, null, 2)}
                              </pre>
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Update Contracts Section */}
        <div className="border border-gray-200 rounded-lg overflow-hidden">
          <div className="bg-gray-50 px-6 py-4 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900">Update Contracts</h2>
            <p className="text-sm text-gray-600 mt-1">On-chain contract configuration and deployment state</p>
          </div>
          <div className="grid grid-cols-2 gap-6 p-6">
            {adminCenter.contracts.map((contract) => (
              <div key={contract.id} className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition">
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <p className="font-semibold text-gray-900">{contract.name}</p>
                    <p className="text-xs text-gray-600 font-mono mt-1">{contract.address}</p>
                  </div>
                  <StatusBadge
                    status={contract.verificationStatus === 'verified' ? 'healthy' : contract.verificationStatus === 'pending' ? 'warning' : 'critical'}
                    label={contract.verificationStatus}
                  />
                </div>
                <div className="space-y-2 text-sm mb-3">
                  <div className="flex items-center justify-between">
                    <span className="text-gray-600">Network:</span>
                    <span className="font-medium text-gray-900">{contract.network}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-gray-600">Version:</span>
                    <span className="font-medium text-gray-900">{contract.version}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-gray-600">Status:</span>
                    <span className={contract.isActive ? 'text-green-700 font-medium' : 'text-gray-600'}>
                      {contract.isActive ? '✓ Active' : 'Inactive'}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-gray-600">Last Update:</span>
                    <span className="text-xs text-gray-500">{contract.lastUpdateTime.toLocaleDateString()}</span>
                  </div>
                </div>
                <button
                  onClick={() => {
                    updateContract(contract.id);
                    setShowDetailView({ type: 'contract', id: contract.id });
                  }}
                  className="w-full btn-secondary flex items-center justify-center gap-2 text-sm"
                >
                  <Edit2 className="w-4 h-4" />
                  View Details
                </button>
              </div>
            ))}
          </div>
        </div>

        {/* Save Config Section */}
        <div className="border border-gray-200 rounded-lg overflow-hidden">
          <div className="bg-gray-50 px-6 py-4 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900">Configuration Management</h2>
            <p className="text-sm text-gray-600 mt-1">Commit changes and track configuration history</p>
          </div>
          <div className="p-6 space-y-4">
            <div className="bg-blue-50 border border-blue-200 rounded p-4">
              <div className="flex items-start justify-between mb-3">
                <div>
                  <p className="font-semibold text-gray-900">Current Configuration State</p>
                  <p className="text-sm text-gray-600 mt-1">
                    {adminCenter.unsavedChanges ? 'You have unsaved changes' : 'All changes saved and active'}
                  </p>
                </div>
                {adminCenter.unsavedChanges && (
                  <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0" />
                )}
              </div>

              {adminCenter.lastSaveTime && (
                <div className="grid grid-cols-2 gap-4 text-sm mb-4">
                  <div>
                    <p className="text-gray-600">Last Saved:</p>
                    <p className="font-medium text-gray-900">{adminCenter.lastSaveTime.toLocaleString()}</p>
                  </div>
                  <div>
                    <p className="text-gray-600">Saved By:</p>
                    <p className="font-medium text-gray-900">{adminCenter.lastSavedBy || 'N/A'}</p>
                  </div>
                </div>
              )}

              <div className="bg-white border border-gray-200 rounded p-3 mb-4">
                <p className="text-xs font-semibold text-gray-700 mb-2">Recent Changes</p>
                <div className="space-y-1 max-h-32 overflow-y-auto">
                  {adminCenter.configChanges.slice(0, 5).map((change) => (
                    <div key={change.id} className="text-xs text-gray-600 flex items-start gap-2">
                      <span className={`inline-block w-2 h-2 rounded-full flex-shrink-0 mt-1 ${change.status === 'active' ? 'bg-green-500' : 'bg-amber-500'}`}></span>
                      <span>{change.description}</span>
                    </div>
                  ))}
                </div>
              </div>

              <button
                onClick={() => setShowSaveConfirmation(true)}
                className="w-full btn-primary flex items-center justify-center gap-2"
                disabled={!adminCenter.unsavedChanges}
              >
                <Save className="w-4 h-4" />
                Save Configuration
              </button>
            </div>
          </div>
        </div>

        {/* View Audit Log Section */}
        <div className="border border-gray-200 rounded-lg overflow-hidden">
          <div className="bg-gray-50 px-6 py-4 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900">View Audit Log</h2>
            <p className="text-sm text-gray-600 mt-1">Full historical record of system actions (searchable and filterable)</p>
          </div>

          {/* Audit Filters */}
          <div className="p-6 bg-gray-50 border-b border-gray-200">
            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-2">
                  <Filter className="w-4 h-4 inline mr-2" />
                  Action Type
                </label>
                <select
                  value={selectedAuditAction || ''}
                  onChange={(e) => setSelectedAuditAction(e.target.value as AuditActionType | null)}
                  className="w-full px-3 py-2 border border-gray-200 rounded text-sm"
                >
                  <option value="">All Actions</option>
                  {allActionTypes.map((type) => (
                    <option key={type} value={type}>
                      {type.replace('_', ' ')}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-2">
                  <Zap className="w-4 h-4 inline mr-2" />
                  Subsystem
                </label>
                <select
                  value={auditSearchSubsystem}
                  onChange={(e) => setAuditSearchSubsystem(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-200 rounded text-sm"
                >
                  <option value="">All Subsystems</option>
                  {allSubsystems.map((subsystem) => (
                    <option key={subsystem} value={subsystem}>
                      {subsystem}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-2">
                  <Clock className="w-4 h-4 inline mr-2" />
                  Clear Filters
                </label>
                <button
                  onClick={() => {
                    setSelectedAuditAction(null);
                    setAuditSearchSubsystem('');
                  }}
                  className="w-full px-3 py-2 border border-gray-200 rounded text-sm font-medium text-gray-700 hover:bg-gray-100"
                >
                  Reset All
                </button>
              </div>
            </div>
          </div>

          {/* Audit Log Table */}
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-100 border-b border-gray-200">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-gray-700">Timestamp</th>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-gray-700">Action Type</th>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-gray-700">Actor</th>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-gray-700">Subsystem</th>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-gray-700">Description</th>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-gray-700">Severity</th>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-gray-700">Action</th>
                </tr>
              </thead>
              <tbody>
                {filteredAudit.map((entry) => (
                  <tr key={entry.id} className="border-b border-gray-200 hover:bg-gray-50">
                    <td className="px-6 py-4 text-sm text-gray-700">{entry.timestamp.toLocaleString()}</td>
                    <td className="px-6 py-4 text-sm">
                      <span className="inline-block bg-purple-100 text-purple-700 px-2 py-1 rounded text-xs font-medium">
                        {entry.actionType.replace('_', ' ')}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-700">{entry.actor}</td>
                    <td className="px-6 py-4 text-sm">
                      <span className="inline-block bg-gray-100 text-gray-700 px-2 py-1 rounded text-xs font-medium">
                        {entry.subsystem}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-700">{entry.description}</td>
                    <td className="px-6 py-4 text-sm">
                      <StatusBadge
                        status={entry.severity === 'critical' ? 'critical' : entry.severity === 'warning' ? 'warning' : 'healthy'}
                        label={entry.severity}
                      />
                    </td>
                    <td className="px-6 py-4 text-sm">
                      <button
                        onClick={() => setShowDetailView({ type: 'audit', id: entry.id })}
                        className="text-blue-600 hover:text-blue-700 font-medium"
                      >
                        View
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {filteredAudit.length === 0 && (
            <div className="p-6 text-center text-gray-600">
              <Search className="w-8 h-8 mx-auto mb-2 opacity-50" />
              <p>No audit log entries match your filters.</p>
            </div>
          )}
        </div>

        {/* Download Replay Report Section */}
        <div className="border border-gray-200 rounded-lg overflow-hidden">
          <div className="bg-gray-50 px-6 py-4 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900">Export & Reports</h2>
            <p className="text-sm text-gray-600 mt-1">Download complete historical snapshot of system behavior</p>
          </div>
          <div className="p-6 space-y-4">
            <div className="bg-green-50 border border-green-200 rounded p-4">
              <div className="flex items-start justify-between mb-3">
                <div>
                  <p className="font-semibold text-gray-900">Replay Report</p>
                  <p className="text-sm text-gray-600 mt-1">Complete execution history and system behavior snapshot</p>
                </div>
                <Download className="w-5 h-5 text-green-700 flex-shrink-0" />
              </div>
              {adminCenter.replayReportUrl && (
                <p className="text-xs text-gray-600 mb-3">
                  Latest report: <span className="font-mono">{adminCenter.replayReportUrl.split('/').pop()}</span>
                </p>
              )}
              <button
                onClick={() => downloadReplayReport()}
                className="w-full btn-primary flex items-center justify-center gap-2"
              >
                <Download className="w-4 h-4" />
                Download Replay Report
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Save Confirmation Modal */}
      {showSaveConfirmation && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-lg max-w-2xl w-full mx-4 p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Save Configuration Changes</h3>

            <div className="space-y-4 mb-6">
              <p className="text-sm text-gray-600">Review the changes that will be saved and activated:</p>

              <div className="bg-gray-50 border border-gray-200 rounded p-4 max-h-48 overflow-y-auto">
                {adminCenter.configChanges.slice(0, 5).map((change) => (
                  <div key={change.id} className="mb-3 pb-3 border-b border-gray-200 last:border-0">
                    <p className="text-sm font-semibold text-gray-900">{change.description}</p>
                    <p className="text-xs text-gray-600 mt-1">
                      {change.timestamp.toLocaleString()} by {change.changedBy}
                    </p>
                  </div>
                ))}
              </div>

              <div className="bg-green-50 border border-green-200 rounded p-3">
                <p className="text-sm text-green-700">
                  <CheckCircle className="w-4 h-4 inline mr-2" />
                  Once saved, these changes will be active immediately.
                </p>
              </div>
            </div>

            <div className="flex gap-3">
              <button
                onClick={() => {
                  saveConfig();
                  setShowSaveConfirmation(false);
                }}
                className="flex-1 btn-primary flex items-center justify-center gap-2"
              >
                <Save className="w-4 h-4" />
                Confirm & Save
              </button>
              <button
                onClick={() => setShowSaveConfirmation(false)}
                className="flex-1 btn-secondary flex items-center justify-center gap-2"
              >
                <X className="w-4 h-4" />
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Detail View Modal */}
      {showDetailView && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-lg max-w-2xl w-full mx-4 p-6 max-h-[80vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-gray-900">
                {showDetailView.type === 'provider' && 'Provider Configuration'}
                {showDetailView.type === 'contract' && 'Contract Details'}
                {showDetailView.type === 'audit' && 'Audit Entry Details'}
              </h3>
              <button
                onClick={() => setShowDetailView(null)}
                className="text-gray-400 hover:text-gray-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {showDetailView.type === 'provider' && (
              <div>
                {adminCenter.providers.find((p) => p.id === showDetailView.id) && (
                  <pre className="bg-gray-50 p-4 rounded border border-gray-200 text-xs overflow-auto max-h-48">
                    {JSON.stringify(
                      adminCenter.providers.find((p) => p.id === showDetailView.id),
                      null,
                      2
                    )}
                  </pre>
                )}
              </div>
            )}

            {showDetailView.type === 'contract' && (
              <div>
                {adminCenter.contracts.find((c) => c.id === showDetailView.id) && (
                  <pre className="bg-gray-50 p-4 rounded border border-gray-200 text-xs overflow-auto max-h-48">
                    {JSON.stringify(
                      adminCenter.contracts.find((c) => c.id === showDetailView.id),
                      null,
                      2
                    )}
                  </pre>
                )}
              </div>
            )}

            {showDetailView.type === 'audit' && (
              <div>
                {adminCenter.auditLog.find((e) => e.id === showDetailView.id) && (
                  <pre className="bg-gray-50 p-4 rounded border border-gray-200 text-xs overflow-auto max-h-48">
                    {JSON.stringify(
                      adminCenter.auditLog.find((e) => e.id === showDetailView.id),
                      null,
                      2
                    )}
                  </pre>
                )}
              </div>
            )}

            <button
              onClick={() => setShowDetailView(null)}
              className="w-full mt-4 btn-secondary"
            >
              Close
            </button>
          </div>
        </div>
      )}
    </Layout>
  );
}
