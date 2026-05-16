import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, Copy, ExternalLink, AlertTriangle, CheckCircle2, Clock, Zap } from 'lucide-react';
import { Layout } from '@/components';
import { useDashboardStore } from '@/store';
import StatusBadge from '@/components/StatusBadge';

export const Execution: React.FC = () => {
  const navigate = useNavigate();
  
  const execution = useDashboardStore((s) => s.executionCenter);
  const runSimulation = useDashboardStore((s) => s.runSimulation);
  const broadcastTrade = useDashboardStore((s) => s.broadcastTrade);
  const retryExecution = useDashboardStore((s) => s.retryExecution);

  const [simulating, setSimulating] = useState(false);
  const [broadcasting, setBroadcasting] = useState(false);
  const [copiedTx, setCopiedTx] = useState(false);
  const [showRpcModal, setShowRpcModal] = useState(false);
  const [replayEndpoint, setReplayEndpoint] = useState('https://rpc.ankr.com/eth_goerli');
  const [replayResponse, setReplayResponse] = useState<string | null>(null);

  const getStateColor = (state: typeof execution.currentState) => {
    switch (state) {
      case 'awaiting_simulation':
        return 'bg-yellow-50 border-yellow-300';
      case 'simulated':
        return 'bg-green-50 border-green-300';
      case 'queued_broadcast':
        return 'bg-blue-50 border-blue-300';
      case 'broadcasting':
        return 'bg-purple-50 border-purple-300';
      case 'confirmed':
        return 'bg-green-100 border-green-400';
      case 'failed':
        return 'bg-red-50 border-red-300';
      case 'partial_success':
        return 'bg-orange-50 border-orange-300';
      default:
        return 'bg-gray-50 border-gray-300';
    }
  };

  const getStateLabel = (state: typeof execution.currentState) => {
    const labels: Record<typeof execution.currentState, string> = {
      awaiting_simulation: 'Awaiting Simulation',
      simulated: 'Simulation Passed',
      queued_broadcast: 'Queued for Broadcast',
      broadcasting: 'Broadcasting to Network',
      confirmed: 'Confirmed On-Chain',
      failed: 'Execution Failed',
      partial_success: 'Partial Success',
    };
    return labels[state];
  };

  const getStateStatusBadge = (state: typeof execution.currentState) => {
    if (['simulated', 'confirmed'].includes(state)) return 'healthy';
    if (['awaiting_simulation', 'queued_broadcast', 'broadcasting'].includes(state)) return 'warning';
    return 'critical';
  };

  const handleSimulate = async () => {
    setSimulating(true);
    await runSimulation(execution.id);
    setSimulating(false);
  };

  const handleBroadcast = async () => {
    setBroadcasting(true);
    await broadcastTrade(execution.id);
    setBroadcasting(false);
  };

  const handleRetry = async () => {
    await retryExecution(execution.id);
  };

  const copyToClipboard = () => {
    if (execution.broadcastState.transactionHash) {
      navigator.clipboard.writeText(execution.broadcastState.transactionHash);
      setCopiedTx(true);
      setTimeout(() => setCopiedTx(false), 2000);
    }
  };

  const chainExplorerUrl = execution.broadcastState.transactionHash ? '#on-chain-outcome' : '';

  return (
    <Layout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate('/opportunities')}
              className="p-2 hover:bg-surface-container rounded-lg transition-colors"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div>
              <h1 className="text-display-lg font-serif text-primary">Execution Center</h1>
              <p className="text-body-md text-on-surface-variant">Live trade execution and settlement tracking</p>
            </div>
          </div>
        </div>

        {/* 0G Integration Proof */}
        <div className="card border-2">
          <div className="p-3 flex items-center justify-between">
            <div>
              <p className="text-label-sm text-on-surface-variant">Proof of 0G integration</p>
              <p className="text-body-md font-semibold">On-chain contracts deployed</p>
            </div>
            <div className="text-right text-sm">
              <div>
                <a className="text-blue-600 underline" href="https://chainscan.0g.ai/address/0x545cd17d890455040593e35018216c906221c371" target="_blank" rel="noreferrer">SignalValidator</a>
              </div>
              <div>
                <a className="text-blue-600 underline" href="https://chainscan.0g.ai/address/0x4c580fb35fbcc2a6d7223984b634cce7ebe730ed" target="_blank" rel="noreferrer">LendingPool</a>
              </div>
              <div>
                <a className="text-blue-600 underline" href="https://chainscan.0g.ai/address/0x8a22f9af206fcc38d00c44dca8b15555785b8a4a" target="_blank" rel="noreferrer">ArbitrageExecutor</a>
              </div>
            </div>
          </div>
        </div>

        {/* Current Execution State */}
        <div className={`card border-2 ${getStateColor(execution.currentState)}`}>
          <div className="flex items-start justify-between">
            <div>
              <p className="text-label-md text-on-surface-variant uppercase tracking-wider mb-2">Execution State</p>
              <h2 className="text-display-md font-serif mb-3">{getStateLabel(execution.currentState)}</h2>
              <p className="text-body-md text-on-surface-variant max-w-2xl">
                {execution.currentState === 'awaiting_simulation' && 'Ready to run pre-flight simulation. This checks whether the trade is safe to execute on-chain.'}
                {execution.currentState === 'simulated' && 'Simulation passed. The trade is approved for broadcast to the network.'}
                {execution.currentState === 'queued_broadcast' && 'Trade queued for broadcast. Will be submitted to the network momentarily.'}
                {execution.currentState === 'broadcasting' && 'Broadcast in progress. Transaction submitted to network, waiting for confirmation.'}
                {execution.currentState === 'confirmed' && 'Trade execution completed on-chain. Settlement record is ready for review.'}
                {execution.currentState === 'failed' && 'Execution failed on-chain. Review the error and decide whether to retry.'}
                {execution.currentState === 'partial_success' && 'Trade partially executed. Some legs completed, others failed or reverted.'}
              </p>
            </div>
            <StatusBadge status={getStateStatusBadge(execution.currentState)} label={execution.currentState} />
          </div>
        </div>

        {/* Pre-Flight Simulation Section */}
        <div className="card border-2 border-blue-300">
          <div className="flex items-center gap-2 mb-4">
            <Zap className="w-5 h-5 text-blue-600" />
            <h2 className="text-headline-sm font-serif">Pre-Flight Simulation</h2>
            <span className="text-label-sm text-on-surface-variant">Determines trade safety</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
            <div>
              <p className="text-label-md text-on-surface-variant mb-2">Simulation Status</p>
              <div className="flex items-center gap-2">
                {execution.simulation.status === 'success' && (
                  <>
                    <CheckCircle2 className="w-6 h-6 text-green-600" />
                    <span className="text-body-lg font-semibold text-green-600">PASSED</span>
                  </>
                )}
                {execution.simulation.status === 'failed' && (
                  <>
                    <AlertTriangle className="w-6 h-6 text-red-600" />
                    <span className="text-body-lg font-semibold text-red-600">FAILED</span>
                  </>
                )}
                {execution.simulation.status === 'pending' && (
                  <>
                    <Clock className="w-6 h-6 text-yellow-600" />
                    <span className="text-body-lg font-semibold text-yellow-600">PENDING</span>
                  </>
                )}
              </div>
            </div>

            <div>
              <p className="text-label-md text-on-surface-variant mb-2">Safe to Execute</p>
              <p className="text-headline-md font-serif">{execution.simulation.pass ? 'Yes' : 'No'}</p>
              {!execution.simulation.pass && execution.simulation.errorMessage && (
                <p className="text-label-sm text-red-600 mt-1">{execution.simulation.errorMessage}</p>
              )}
            </div>
          </div>

          {execution.simulation.executedAt && (
            <p className="text-label-sm text-on-surface-variant mb-3">
              Simulated at {new Date(execution.simulation.executedAt).toLocaleString()}
            </p>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div>
              <p className="text-label-md text-on-surface-variant">Expected Output</p>
              <p className="text-headline-sm font-serif text-primary">{execution.simulation.expectedOutput}</p>
              <p className="text-label-sm text-on-surface-variant mt-1">${execution.simulation.expectedAmount.toLocaleString(undefined, { maximumFractionDigits: 2 })}</p>
            </div>

            <div>
              <p className="text-label-md text-on-surface-variant">Estimated Gas</p>
              <p className="text-headline-sm font-serif text-primary">{execution.simulation.gasEstimatedUnits.toLocaleString()} units</p>
              <p className="text-label-sm text-on-surface-variant mt-1">~{(execution.simulation.gasEstimatedUnits / 1000).toFixed(1)}k Gwei</p>
            </div>
          </div>

          {execution.simulation.warnings.length > 0 && (
            <div className="mt-4 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
              <p className="text-label-md font-semibold text-yellow-900 mb-2">Warnings</p>
              <ul className="space-y-1">
                {execution.simulation.warnings.map((w, i) => (
                  <li key={i} className="text-label-sm text-yellow-800">• {w}</li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {/* Gas Estimate Section */}
        <div className="card border-2 border-purple-300">
          <div className="flex items-center gap-2 mb-4">
            <Zap className="w-5 h-5 text-purple-600" />
            <h2 className="text-headline-sm font-serif">Gas Cost Analysis</h2>
            <span className="text-label-sm text-on-surface-variant">Execution cost & profitability</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div>
              <p className="text-label-md text-on-surface-variant">Gas Usage</p>
              <p className="text-headline-sm font-serif">{execution.gasEstimate.gasUsageUnits.toLocaleString()}</p>
              <p className="text-label-sm text-on-surface-variant mt-1">units</p>
            </div>

            <div>
              <p className="text-label-md text-on-surface-variant">Gas Price</p>
              <p className="text-headline-sm font-serif">{execution.gasEstimate.gasPriceWei.toFixed(0)}</p>
              <p className="text-label-sm text-on-surface-variant mt-1">Gwei</p>
            </div>

            <div>
              <p className="text-label-md text-on-surface-variant">Total Fee</p>
              <p className="text-headline-sm font-serif">${execution.gasEstimate.totalFeeUSD.toFixed(2)}</p>
              <p className="text-label-sm text-on-surface-variant mt-1">{execution.gasEstimate.totalFeeETH.toFixed(4)} ETH</p>
            </div>

            <div className={`p-4 rounded-lg border ${execution.gasEstimate.remainsProfitable ? 'bg-green-50 border-green-300' : 'bg-red-50 border-red-300'}`}>
              <p className="text-label-md text-on-surface-variant mb-1">Profit After Gas</p>
              <p className={`text-headline-sm font-serif ${execution.gasEstimate.remainsProfitable ? 'text-green-600' : 'text-red-600'}`}>
                ${execution.gasEstimate.profitAfterGasUSD.toFixed(2)}
              </p>
              <p className={`text-label-sm mt-1 ${execution.gasEstimate.remainsProfitable ? 'text-green-600' : 'text-red-600'}`}>
                {execution.gasEstimate.profitMarginPct.toFixed(1)}% margin
              </p>
            </div>
          </div>

          <div className="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-lg">
            <p className={`text-label-md font-semibold ${execution.gasEstimate.remainsProfitable ? 'text-green-900' : 'text-red-900'}`}>
              {execution.gasEstimate.remainsProfitable
                ? '✓ Trade remains profitable after all gas costs'
                : '✗ Trade becomes unprofitable after gas costs - consider cancelling'}
            </p>
          </div>
        </div>

        {/* Broadcast State Section */}
        <div className="card border-2 border-indigo-300">
          <div className="flex items-center gap-2 mb-4">
            <Clock className="w-5 h-5 text-indigo-600" />
            <h2 className="text-headline-sm font-serif">Broadcast State</h2>
            <span className="text-label-sm text-on-surface-variant">Transaction journey</span>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
            {['not_sent', 'submitted', 'pending', 'mined'].map((status) => (
              <div
                key={status}
                className={`p-3 rounded-lg border ${
                  ['not_sent', 'submitted', 'pending', 'mined'].indexOf(execution.broadcastState.status) >=
                  ['not_sent', 'submitted', 'pending', 'mined'].indexOf(status as any)
                    ? 'bg-green-50 border-green-300'
                    : 'bg-gray-50 border-gray-300'
                }`}
              >
                <p className="text-label-sm text-on-surface-variant capitalize">{status.replace('_', ' ')}</p>
                {execution.broadcastState.status === status && (
                  <p className="text-label-md font-semibold text-green-600 mt-1">✓ Current</p>
                )}
              </div>
            ))}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {execution.broadcastState.submittedAt && (
              <div>
                <p className="text-label-md text-on-surface-variant">Submitted At</p>
                <p className="text-body-md mt-1">{new Date(execution.broadcastState.submittedAt).toLocaleString()}</p>
              </div>
            )}

            {execution.broadcastState.minedAt && (
              <div>
                <p className="text-label-md text-on-surface-variant">Mined At</p>
                <p className="text-body-md mt-1">{new Date(execution.broadcastState.minedAt).toLocaleString()}</p>
              </div>
            )}

            {execution.broadcastState.confirmations !== undefined && (
              <div>
                <p className="text-label-md text-on-surface-variant">Confirmations</p>
                <p className="text-body-md mt-1">{execution.broadcastState.confirmations} block(s)</p>
              </div>
            )}

            {execution.broadcastState.blockNumber && (
              <div>
                <p className="text-label-md text-on-surface-variant">Block Number</p>
                <p className="text-body-md mt-1">#{execution.broadcastState.blockNumber.toLocaleString()}</p>
              </div>
            )}
          </div>
        </div>

        {/* Transaction Hash Section */}
        {execution.broadcastState.transactionHash && (
          <div className="card bg-gray-50 border-2 border-gray-300">
            <div className="flex items-center justify-between mb-3">
              <div>
                <p className="text-label-md text-on-surface-variant mb-2">Transaction Hash</p>
                <p className="text-body-md font-mono text-primary truncate">{execution.broadcastState.transactionHash}</p>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={copyToClipboard}
                  className="p-3 hover:bg-white rounded-lg transition-colors border border-outline-variant"
                  title="Copy transaction hash"
                >
                  <Copy className="w-5 h-5" />
                </button>
                <a
                  href={chainExplorerUrl}
                  className="p-3 hover:bg-white rounded-lg transition-colors border border-outline-variant flex items-center gap-1"
                >
                  <ExternalLink className="w-5 h-5" />
                </a>
              </div>
            </div>
            {copiedTx && (
              <p className="text-label-sm text-green-600">✓ Copied to clipboard</p>
            )}
          </div>
        )}

        {/* Replay logged network call */}
        {execution.lastRpcPayload && (
          <div className="card border-2 border-gray-200">
            <div className="flex items-center justify-between mb-3">
              <div>
                <p className="text-label-md text-on-surface-variant mb-1">Replay Logged Network Call</p>
                <p className="text-body-sm text-on-surface-variant">View the RPC/receipt recorded during broadcast for replay or download.</p>
              </div>
              <div className="flex items-center gap-2">
                <button onClick={() => setShowRpcModal(true)} className="btn-primary">View / Replay</button>
                <button
                  onClick={() => {
                    // download the stored payload/receipt
                    const blob = new Blob([JSON.stringify(execution.lastRpcPayload, null, 2)], { type: 'application/json' });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `rpc-replay-${execution.broadcastState.transactionHash || 'demo'}.json`;
                    document.body.appendChild(a);
                    a.click();
                    a.remove();
                    URL.revokeObjectURL(url);
                  }}
                  className="btn-secondary"
                >
                  Download Receipt
                </button>
              </div>
            </div>
          </div>
        )}

        {showRpcModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-40">
            <div className="bg-white rounded-lg w-11/12 md:w-2/3 p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-headline-sm font-serif">RPC Payload & Receipt</h3>
                <button onClick={() => setShowRpcModal(false)} className="btn-secondary">Close</button>
              </div>
              <div className="mb-4">
                <label className="text-label-sm">Replay Endpoint</label>
                <input className="w-full p-2 border rounded mt-1 mb-3" value={replayEndpoint} onChange={(e) => setReplayEndpoint(e.target.value)} />
                <pre className="whitespace-pre-wrap text-sm bg-gray-100 p-3 rounded">{JSON.stringify(execution.lastRpcPayload, null, 2)}</pre>
                {replayResponse && (
                  <div className="mt-3 p-2 bg-gray-50 border rounded text-xs">
                    <p className="font-semibold">Replay Response</p>
                    <pre className="max-h-40 overflow-auto">{replayResponse}</pre>
                  </div>
                )}
              </div>
              <div className="flex gap-2 justify-end">
                <button
                  onClick={() => {
                    navigator.clipboard.writeText(JSON.stringify(execution.lastRpcPayload, null, 2));
                  }}
                  className="btn-secondary"
                >
                  Copy Payload
                </button>
                <button
                  onClick={() => {
                    const blob = new Blob([JSON.stringify(execution.lastRpcPayload, null, 2)], { type: 'application/json' });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `rpc-replay-${execution.broadcastState.transactionHash || 'demo'}.json`;
                    document.body.appendChild(a);
                    a.click();
                    a.remove();
                    URL.revokeObjectURL(url);
                  }}
                  className="btn-primary"
                >
                  Download
                </button>
                <button
                  onClick={async () => {
                    try {
                      setReplayResponse('Running...');
                      const rpc = execution.lastRpcPayload?.rpc || execution.lastRpcPayload || execution.broadcastState.transactionHash;
                      const body = rpc?.params ? rpc : execution.lastRpcPayload;
                      const res = await fetch(replayEndpoint, { method: 'POST', body: JSON.stringify(body), headers: { 'Content-Type': 'application/json' } });
                      const text = await res.text();
                      setReplayResponse(text);
                    } catch (err: any) {
                      setReplayResponse(String(err));
                    }
                  }}
                  className="btn-secondary"
                >
                  Replay Now
                </button>
              </div>
            </div>
          </div>
        )}

        {/* On-Chain Outcome Section */}
        <div id="on-chain-outcome" className={`card border-2 ${
          execution.onChainOutcome.status === 'success'
            ? 'bg-green-50 border-green-300'
            : execution.onChainOutcome.status === 'reverted'
              ? 'bg-red-50 border-red-300'
              : 'bg-yellow-50 border-yellow-300'
        }`}>
          <div className="flex items-center gap-2 mb-4">
            {execution.onChainOutcome.status === 'success' && (
              <>
                <CheckCircle2 className="w-5 h-5 text-green-600" />
                <h2 className="text-headline-sm font-serif text-green-900">On-Chain Outcome</h2>
              </>
            )}
            {execution.onChainOutcome.status === 'reverted' && (
              <>
                <AlertTriangle className="w-5 h-5 text-red-600" />
                <h2 className="text-headline-sm font-serif text-red-900">On-Chain Outcome</h2>
              </>
            )}
            {!['success', 'reverted'].includes(execution.onChainOutcome.status) && (
              <>
                <Clock className="w-5 h-5 text-yellow-600" />
                <h2 className="text-headline-sm font-serif text-yellow-900">On-Chain Outcome</h2>
              </>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div>
              <p className="text-label-md text-on-surface-variant">Status</p>
              <p className="text-headline-sm font-serif mt-1 capitalize">{execution.onChainOutcome.status.replace('_', ' ').toUpperCase()}</p>
            </div>

            {execution.onChainOutcome.blockNumber && (
              <div>
                <p className="text-label-md text-on-surface-variant">Block Number</p>
                <p className="text-headline-sm font-serif mt-1">#{execution.onChainOutcome.blockNumber.toLocaleString()}</p>
              </div>
            )}

            {execution.onChainOutcome.gasUsedActual && (
              <div>
                <p className="text-label-md text-on-surface-variant">Actual Gas Used</p>
                <p className="text-headline-sm font-serif mt-1">{execution.onChainOutcome.gasUsedActual.toLocaleString()}</p>
              </div>
            )}

            {execution.onChainOutcome.actualOutput && (
              <div>
                <p className="text-label-md text-on-surface-variant">Actual Output</p>
                <p className="text-headline-sm font-serif mt-1">${execution.onChainOutcome.actualOutput.toLocaleString(undefined, { maximumFractionDigits: 2 })}</p>
              </div>
            )}
          </div>

          {execution.onChainOutcome.errorReason && (
            <div className="p-3 bg-red-100 border border-red-300 rounded-lg">
              <p className="text-label-md font-semibold text-red-900">Error</p>
              <p className="text-label-sm text-red-800 mt-1">{execution.onChainOutcome.errorReason}</p>
            </div>
          )}

          {execution.onChainOutcome.settledAt && (
            <p className="text-label-sm text-on-surface-variant mt-4">
              Settled at {new Date(execution.onChainOutcome.settledAt).toLocaleString()}
            </p>
          )}
        </div>

        {/* Action Buttons */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
          <button
            onClick={handleSimulate}
            disabled={simulating}
            className="btn-primary disabled:opacity-50"
          >
            {simulating ? 'Running Simulation...' : 'Simulate'}
          </button>

          <button
            onClick={handleBroadcast}
            disabled={broadcasting || !execution.simulation.pass}
            className="btn-primary disabled:opacity-50"
          >
            {broadcasting ? 'Broadcasting...' : 'Broadcast'}
          </button>

          {['failed', 'partial_success'].includes(execution.currentState) && (
            <button onClick={handleRetry} className="btn-secondary">
              Retry Execution
            </button>
          )}

          {execution.broadcastState.transactionHash && (
            <a
              href={chainExplorerUrl}
              className="btn-secondary flex items-center justify-center gap-2"
            >
              View on Chain
              <ExternalLink className="w-4 h-4" />
            </a>
          )}

          <button onClick={() => navigate('/opportunities')} className="btn-secondary">
            Back to Queue
          </button>
        </div>

        {/* Decision Help */}
        <div className="card bg-blue-50 border-2 border-blue-300">
          <h3 className="text-headline-sm font-serif mb-3 text-blue-900">Decision Checklist</h3>
          <ul className="space-y-2 text-label-md">
            <li className={`flex items-start gap-2 ${execution.simulation.pass ? 'text-green-700' : 'text-gray-600'}`}>
              <span className={`mt-0.5 ${execution.simulation.pass ? '✓' : '○'}`}></span>
              <span>Did the simulation pass?</span>
            </li>
            <li className={`flex items-start gap-2 ${['queued_broadcast', 'broadcasting', 'confirmed'].includes(execution.currentState) ? 'text-green-700' : 'text-gray-600'}`}>
              <span className={`mt-0.5 ${['queued_broadcast', 'broadcasting', 'confirmed'].includes(execution.currentState) ? '✓' : '○'}`}></span>
              <span>Was the trade broadcast?</span>
            </li>
            <li className={`flex items-start gap-2 ${execution.onChainOutcome.status === 'success' ? 'text-green-700' : 'text-gray-600'}`}>
              <span className={`mt-0.5 ${execution.onChainOutcome.status === 'success' ? '✓' : '○'}`}></span>
              <span>What happened on-chain?</span>
            </li>
          </ul>
        </div>
      </div>
    </Layout>
  );
};

export default Execution;

