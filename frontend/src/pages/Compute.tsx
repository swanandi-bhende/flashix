import React, { useState } from 'react';
import { useDashboardStore } from '@/store';
import StatusBadge from '@/components/StatusBadge';
import Layout from '@/components/Layout';
import {
  CheckCircle,
  AlertTriangle,
  XCircle,
  Clock,
  Shield,
  Link2,
  RefreshCw,
  Play,
  Eye,
  Key,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';

export default function Compute() {
  const { computeCenter, verifyPayload, replayInference, viewTrace, inspectSignature } = useDashboardStore();
  const [expandedRequest, setExpandedRequest] = useState<string | null>(null);
  const [selectedAction, setSelectedAction] = useState<{ type: 'verify' | 'replay' | 'trace' | 'signature'; requestId: string } | null>(null);

  const sortedRequests = [...computeCenter.inferenceRequests].sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime());

  // Summary metrics
  const totalRequests = computeCenter.inferenceRequests.length;
  const validatedRequests = computeCenter.validations.filter((v) => v.status === 'passed').length;
  const verifiedSignatures = computeCenter.signatures.filter((s) => s.signatureStatus === 'verified').length;
  const linkedTraces = computeCenter.traces.length;

  const healthColors = {
    green: 'text-green-700 bg-green-50 border-green-200',
    elevated: 'text-amber-700 bg-amber-50 border-amber-200',
    blocked: 'text-red-700 bg-red-50 border-red-200',
  };

  const handleVerifyPayload = async (requestId: string) => {
    await verifyPayload(requestId);
    setSelectedAction({ type: 'verify', requestId });
  };

  const handleReplayInference = async (requestId: string) => {
    await replayInference(requestId);
    setSelectedAction({ type: 'replay', requestId });
  };

  const handleViewTrace = (requestId: string) => {
    viewTrace(requestId);
    setSelectedAction({ type: 'trace', requestId });
  };

  const handleInspectSignature = (requestId: string) => {
    inspectSignature(requestId);
    setSelectedAction({ type: 'signature', requestId });
  };

  return (
    <Layout>
      <div className="space-y-8">
        {/* Header */}
        <div className="border-b border-gray-200 pb-6">
          <h1 className="text-3xl font-serif font-bold text-gray-900 mb-2">Compute & TEE</h1>
          <p className="text-gray-600">Central inspection screen for inference requests, validation, signatures, and trace linking</p>
        </div>

        {/* Health Summary - Four Key Questions */}
        <div className="grid grid-cols-4 gap-4">
          <div className={`border rounded-lg p-4 ${healthColors[computeCenter.overallHealth]}`}>
            <div className="flex items-center justify-between mb-2">
              <h3 className="font-semibold text-sm">TEE Entry Status</h3>
              {totalRequests > 0 ? <CheckCircle className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
            </div>
            <p className="text-xs mb-1">Did request enter TEE correctly?</p>
            <p className="text-lg font-bold">{totalRequests}</p>
            <p className="text-xs mt-1 opacity-75">Requests submitted</p>
          </div>

          <div className={`border rounded-lg p-4 ${healthColors[computeCenter.overallHealth]}`}>
            <div className="flex items-center justify-between mb-2">
              <h3 className="font-semibold text-sm">Validation Status</h3>
              {validatedRequests > 0 ? <CheckCircle className="w-4 h-4" /> : <AlertTriangle className="w-4 h-4" />}
            </div>
            <p className="text-xs mb-1">Did validation pass?</p>
            <p className="text-lg font-bold">{validatedRequests} of {totalRequests}</p>
            <p className="text-xs mt-1 opacity-75">Validation passed</p>
          </div>

          <div className={`border rounded-lg p-4 ${healthColors[computeCenter.overallHealth]}`}>
            <div className="flex items-center justify-between mb-2">
              <h3 className="font-semibold text-sm">Signature Verification</h3>
              {verifiedSignatures > 0 ? <Shield className="w-4 h-4" /> : <AlertTriangle className="w-4 h-4" />}
            </div>
            <p className="text-xs mb-1">Was signature verified?</p>
            <p className="text-lg font-bold">{verifiedSignatures} of {totalRequests}</p>
            <p className="text-xs mt-1 opacity-75">Signatures verified</p>
          </div>

          <div className={`border rounded-lg p-4 ${healthColors[computeCenter.overallHealth]}`}>
            <div className="flex items-center justify-between mb-2">
              <h3 className="font-semibold text-sm">Trace Linking</h3>
              {linkedTraces > 0 ? <Link2 className="w-4 h-4" /> : <Clock className="w-4 h-4" />}
            </div>
            <p className="text-xs mb-1">What trace links output?</p>
            <p className="text-lg font-bold">{linkedTraces}</p>
            <p className="text-xs mt-1 opacity-75">Traces linked</p>
          </div>
        </div>

        {/* Latest Inference Requests */}
        <div className="border border-gray-200 rounded-lg overflow-hidden">
          <div className="bg-gray-50 px-6 py-4 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900">Latest Inference Requests</h2>
            <p className="text-sm text-gray-600 mt-1">Starting point for every trusted decision</p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-100 border-b border-gray-200">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-gray-700">Request ID</th>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-gray-700">Timestamp</th>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-gray-700">Source Opportunity</th>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-gray-700">Status</th>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-gray-700">Processing Time</th>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-gray-700">Actions</th>
                </tr>
              </thead>
              <tbody>
                {sortedRequests.map((request) => (
                  <React.Fragment key={request.id}>
                    <tr className="border-b border-gray-200 hover:bg-gray-50">
                      <td className="px-6 py-4 text-sm font-mono text-blue-600">{request.id}</td>
                      <td className="px-6 py-4 text-sm text-gray-700">{request.timestamp.toLocaleString()}</td>
                      <td className="px-6 py-4 text-sm text-gray-700">{request.sourceOpportunityId}</td>
                      <td className="px-6 py-4 text-sm">
                        <StatusBadge
                          status={
                            request.status === 'completed'
                              ? 'healthy'
                              : request.status === 'failed'
                              ? 'critical'
                              : request.status === 'validated' || request.status === 'processing'
                              ? 'warning'
                              : 'healthy'
                          }
                          label={request.status}
                        />
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-700">
                        {request.processingTimeMs ? `${request.processingTimeMs}ms` : '-'}
                      </td>
                      <td className="px-6 py-4 text-sm space-x-2">
                        <button
                          onClick={() => setExpandedRequest(expandedRequest === request.id ? null : request.id)}
                          className="inline-flex items-center text-blue-600 hover:text-blue-700 font-medium"
                        >
                          {expandedRequest === request.id ? (
                            <ChevronUp className="w-4 h-4" />
                          ) : (
                            <ChevronDown className="w-4 h-4" />
                          )}
                        </button>
                      </td>
                    </tr>
                    {expandedRequest === request.id && (
                      <tr className="bg-blue-50 border-b border-gray-200">
                        <td colSpan={6} className="px-6 py-4">
                          <div className="grid grid-cols-2 gap-6">
                            <div>
                              <h4 className="font-semibold text-gray-900 mb-2">Payload Details</h4>
                              <pre className="bg-white p-3 rounded border border-gray-200 text-xs overflow-auto max-h-40">
                                {JSON.stringify(request.payload, null, 2)}
                              </pre>
                            </div>
                            <div className="space-y-3">
                              <button
                                onClick={() => handleVerifyPayload(request.id)}
                                className="w-full btn-primary flex items-center justify-center gap-2"
                              >
                                <RefreshCw className="w-4 h-4" />
                                Verify Payload
                              </button>
                              <button
                                onClick={() => handleReplayInference(request.id)}
                                className="w-full btn-secondary flex items-center justify-center gap-2"
                              >
                                <Play className="w-4 h-4" />
                                Replay Inference
                              </button>
                              <button
                                onClick={() => handleViewTrace(request.id)}
                                className="w-full btn-secondary flex items-center justify-center gap-2"
                              >
                                <Eye className="w-4 h-4" />
                                Open Trace
                              </button>
                              <button
                                onClick={() => handleInspectSignature(request.id)}
                                className="w-full btn-secondary flex items-center justify-center gap-2"
                              >
                                <Key className="w-4 h-4" />
                                Inspect Signature
                              </button>
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

        {/* Payload Validation Section */}
        <div className="border border-gray-200 rounded-lg overflow-hidden">
          <div className="bg-gray-50 px-6 py-4 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900">Payload Validation</h2>
            <p className="text-sm text-gray-600 mt-1">Whether incoming data was accepted by TEE validation logic</p>
          </div>
          <div className="grid grid-cols-2 gap-6 p-6">
            {computeCenter.validations.map((validation) => {
              const request = computeCenter.inferenceRequests.find((r) => r.id === validation.requestId);
              return (
                <div key={validation.requestId} className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition">
                  <div className="flex items-start justify-between mb-3">
                    <div>
                      <p className="font-semibold text-gray-900">{validation.requestId}</p>
                      <p className="text-sm text-gray-600 mt-1">{request?.sourceOpportunityId}</p>
                    </div>
                    <StatusBadge
                      status={validation.status === 'passed' ? 'healthy' : 'critical'}
                      label={validation.status}
                    />
                  </div>
                  <div className="space-y-2 text-sm">
                    <div className="flex items-center justify-between">
                      <span className="text-gray-600">Schema Valid:</span>
                      <span className={validation.schemaValid ? 'text-green-700 font-medium' : 'text-red-700 font-medium'}>
                        {validation.schemaValid ? '✓ Yes' : '✗ No'}
                      </span>
                    </div>
                    {validation.requiredFieldsMissing.length > 0 && (
                      <div className="bg-red-50 border border-red-200 rounded p-2">
                        <p className="text-red-700 font-medium text-xs mb-1">Missing Fields:</p>
                        <p className="text-red-600 text-xs">{validation.requiredFieldsMissing.join(', ')}</p>
                      </div>
                    )}
                    {validation.malformedInputs.length > 0 && (
                      <div className="bg-red-50 border border-red-200 rounded p-2">
                        <p className="text-red-700 font-medium text-xs mb-1">Malformed Inputs:</p>
                        <p className="text-red-600 text-xs">{validation.malformedInputs.join(', ')}</p>
                      </div>
                    )}
                    {validation.rejectionReason && (
                      <div className="bg-red-50 border border-red-200 rounded p-2">
                        <p className="text-red-700 font-medium text-xs mb-1">Rejection Reason:</p>
                        <p className="text-red-600 text-xs">{validation.rejectionReason}</p>
                      </div>
                    )}
                    <p className="text-gray-500 text-xs mt-3">Validated: {validation.validatedAt.toLocaleTimeString()}</p>
                  </div>
                  <button
                    onClick={() => handleVerifyPayload(validation.requestId)}
                    className="w-full mt-3 btn-secondary flex items-center justify-center gap-2 text-sm"
                  >
                    <RefreshCw className="w-4 h-4" />
                    Verify Now
                  </button>
                </div>
              );
            })}
          </div>
        </div>

        {/* Signature Checks Section */}
        <div className="border border-gray-200 rounded-lg overflow-hidden">
          <div className="bg-gray-50 px-6 py-4 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900">Signature Checks</h2>
            <p className="text-sm text-gray-600 mt-1">Cryptographic proof that TEE output can be trusted downstream</p>
          </div>
          <div className="grid grid-cols-2 gap-6 p-6">
            {computeCenter.signatures.map((signature) => (
              <div key={signature.requestId} className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition">
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <p className="font-semibold text-gray-900">{signature.requestId}</p>
                    <p className="text-sm text-gray-600 font-mono mt-1">{signature.signerIdentity}</p>
                  </div>
                  <StatusBadge
                    status={
                      signature.signatureStatus === 'verified'
                        ? 'healthy'
                        : signature.signatureStatus === 'pending'
                        ? 'warning'
                        : 'critical'
                    }
                    label={signature.signatureStatus}
                  />
                </div>
                <div className="space-y-2 text-sm">
                  <div className="flex items-center justify-between">
                    <span className="text-gray-600">Verification Result:</span>
                    <span className={signature.verificationResult ? 'text-green-700 font-medium' : 'text-red-700 font-medium'}>
                      {signature.verificationResult ? '✓ Valid' : '✗ Invalid'}
                    </span>
                  </div>
                  {signature.mismatchWarning && (
                    <div className="bg-amber-50 border border-amber-200 rounded p-2">
                      <p className="text-amber-700 font-medium text-xs mb-1">Warning:</p>
                      <p className="text-amber-600 text-xs">{signature.mismatchWarning}</p>
                    </div>
                  )}
                  {signature.verifiedAt && (
                    <p className="text-gray-500 text-xs mt-3">Verified: {signature.verifiedAt.toLocaleTimeString()}</p>
                  )}
                </div>
                <button
                  onClick={() => handleInspectSignature(signature.requestId)}
                  className="w-full mt-3 btn-secondary flex items-center justify-center gap-2 text-sm"
                >
                  <Key className="w-4 h-4" />
                  Inspect Details
                </button>
              </div>
            ))}
          </div>
        </div>

        {/* Trace Linking Section */}
        <div className="border border-gray-200 rounded-lg overflow-hidden">
          <div className="bg-gray-50 px-6 py-4 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900">Trace Linking</h2>
            <p className="text-sm text-gray-600 mt-1">Connect inference result back to reasoning and execution path</p>
          </div>
          {computeCenter.traces.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-100 border-b border-gray-200">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-gray-700">Request ID</th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-gray-700">Opportunity ID</th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-gray-700">Trace ID</th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-gray-700">Linked Decision</th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-gray-700">Downstream Consumer</th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-gray-700">Linked Stage</th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-gray-700">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {computeCenter.traces.map((trace) => (
                    <tr key={trace.requestId} className="border-b border-gray-200 hover:bg-gray-50">
                      <td className="px-6 py-4 text-sm font-mono text-blue-600">{trace.requestId}</td>
                      <td className="px-6 py-4 text-sm text-gray-700">{trace.opportunityId}</td>
                      <td className="px-6 py-4 text-sm font-mono text-gray-600">{trace.traceId}</td>
                      <td className="px-6 py-4 text-sm">
                        <span className="inline-block bg-blue-50 border border-blue-200 rounded px-2 py-1 text-blue-700 text-xs font-medium">
                          {trace.linkedDecisionRecord.decision}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-700">{trace.downstreamConsumer}</td>
                      <td className="px-6 py-4 text-sm">
                        <span className="inline-block bg-green-50 border border-green-200 rounded px-2 py-1 text-green-700 text-xs font-medium">
                          {trace.linkedStage}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-sm">
                        <button
                          onClick={() => handleViewTrace(trace.requestId)}
                          className="text-blue-600 hover:text-blue-700 font-medium inline-flex items-center gap-1"
                        >
                          <Eye className="w-4 h-4" />
                          View
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="p-6 text-center text-gray-600">
              <Clock className="w-8 h-8 mx-auto mb-2 opacity-50" />
              <p>No traces linked yet. Traces appear as inference results are processed and routed downstream.</p>
            </div>
          )}
        </div>

        {/* Action Result Modal */}
        {selectedAction && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="bg-white rounded-lg shadow-lg max-w-2xl w-full mx-4 p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">
                {selectedAction.type === 'verify' && 'Payload Verification Result'}
                {selectedAction.type === 'replay' && 'Inference Replay Result'}
                {selectedAction.type === 'trace' && 'Trace Record Details'}
                {selectedAction.type === 'signature' && 'Signature Details'}
              </h3>

              {selectedAction.type === 'verify' && (
                <div className="space-y-3">
                  <div className="bg-green-50 border border-green-200 rounded p-4">
                    <p className="text-green-700 font-semibold">✓ Payload verification passed</p>
                    <p className="text-green-600 text-sm mt-1">The request {selectedAction.requestId} has been validated against the schema and all required fields are present.</p>
                  </div>
                </div>
              )}

              {selectedAction.type === 'replay' && (
                <div className="space-y-3">
                  <div className="bg-green-50 border border-green-200 rounded p-4">
                    <p className="text-green-700 font-semibold">✓ Inference replay completed</p>
                    <p className="text-green-600 text-sm mt-1">The request {selectedAction.requestId} has been reprocessed. Comparing original vs new result shows model behavior is stable.</p>
                  </div>
                </div>
              )}

              {selectedAction.type === 'trace' && (
                <div className="space-y-3">
                  {computeCenter.traces.find((t) => t.requestId === selectedAction.requestId) && (
                    <div>
                      <p className="text-sm text-gray-600 mb-3">Trace linked to this inference output:</p>
                      <pre className="bg-gray-50 p-4 rounded border border-gray-200 text-xs overflow-auto max-h-48">
                        {JSON.stringify(
                          computeCenter.traces.find((t) => t.requestId === selectedAction.requestId),
                          null,
                          2
                        )}
                      </pre>
                    </div>
                  )}
                </div>
              )}

              {selectedAction.type === 'signature' && (
                <div className="space-y-3">
                  {computeCenter.signatures.find((s) => s.requestId === selectedAction.requestId) && (
                    <div>
                      <p className="text-sm text-gray-600 mb-3">Signature verification metadata:</p>
                      <pre className="bg-gray-50 p-4 rounded border border-gray-200 text-xs overflow-auto max-h-48">
                        {JSON.stringify(
                          computeCenter.signatures.find((s) => s.requestId === selectedAction.requestId),
                          null,
                          2
                        )}
                      </pre>
                    </div>
                  )}
                </div>
              )}

              <button
                onClick={() => setSelectedAction(null)}
                className="w-full mt-4 btn-secondary"
              >
                Close
              </button>
            </div>
          </div>
        )}
      </div>
    </Layout>
  );
}
