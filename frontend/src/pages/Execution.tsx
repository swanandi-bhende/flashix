import React from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { Layout } from '@/components';

export const Execution: React.FC = () => {
  const navigate = useNavigate();

  const recentExecutions = [
    {
      id: '1',
      txHash: '0x1234...5678',
      pair: 'ETH/USDC',
      status: 'confirmed',
      gasCost: 120,
      profit: 2450,
      timestamp: '2 minutes ago',
    },
    {
      id: '2',
      txHash: '0x9abc...def0',
      pair: 'DAI/USDC',
      status: 'confirmed',
      gasCost: 95,
      profit: 1850,
      timestamp: '8 minutes ago',
    },
    {
      id: '3',
      txHash: '0x5def...1234',
      pair: 'USDT/USDC',
      status: 'failed',
      gasCost: 85,
      profit: 0,
      timestamp: '18 minutes ago',
    },
  ];

  const getStatusBadgeClass = (status: string) => {
    switch (status) {
      case 'confirmed':
        return 'bg-green-100 text-green-900';
      case 'pending':
        return 'bg-yellow-100 text-yellow-900';
      case 'failed':
        return 'bg-red-100 text-red-900';
      default:
        return 'bg-gray-100 text-gray-900';
    }
  };

  return (
    <Layout>
      <div className="space-y-8">
        <div className="flex items-center gap-4 mb-6">
          <button
            onClick={() => navigate('/')}
            className="p-2 hover:bg-surface-container rounded-lg transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <h1 className="text-display-lg font-serif text-primary">Execution History</h1>
            <p className="text-body-md text-on-surface-variant">
              Track all executed trades, gas costs, and profitability
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          <div className="card">
            <p className="text-label-md text-on-surface-variant mb-2">Executed Today</p>
            <p className="text-headline-md font-serif text-primary">142</p>
            <p className="text-label-sm text-on-surface-variant mt-2">Success rate: 94.4%</p>
          </div>
          <div className="card">
            <p className="text-label-md text-on-surface-variant mb-2">Total Profit</p>
            <p className="text-headline-md font-serif text-primary">$45.8K</p>
            <p className="text-label-sm text-on-surface-variant mt-2">Net of gas costs</p>
          </div>
          <div className="card">
            <p className="text-label-md text-on-surface-variant mb-2">Avg Gas Cost</p>
            <p className="text-headline-md font-serif text-primary">$108</p>
            <p className="text-label-sm text-on-surface-variant mt-2">Current: $95-120</p>
          </div>
          <div className="card">
            <p className="text-label-md text-on-surface-variant mb-2">Failed Executions</p>
            <p className="text-headline-md font-serif text-error">8</p>
            <p className="text-label-sm text-on-surface-variant mt-2">5.6% failure rate</p>
          </div>
        </div>

        <div className="card">
          <h2 className="text-headline-sm font-serif mb-6">Recent Executions</h2>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-outline-variant/30">
                  <th className="text-left py-3 px-4 text-label-md text-on-surface-variant">TX Hash</th>
                  <th className="text-left py-3 px-4 text-label-md text-on-surface-variant">Pair</th>
                  <th className="text-right py-3 px-4 text-label-md text-on-surface-variant">Gas Cost</th>
                  <th className="text-right py-3 px-4 text-label-md text-on-surface-variant">Profit</th>
                  <th className="text-center py-3 px-4 text-label-md text-on-surface-variant">Status</th>
                  <th className="text-right py-3 px-4 text-label-md text-on-surface-variant">Time</th>
                </tr>
              </thead>
              <tbody>
                {recentExecutions.map((exec) => (
                  <tr key={exec.id} className="border-b border-outline-variant/20 hover:bg-surface-container transition-colors">
                    <td className="py-4 px-4 font-body-md text-primary cursor-pointer hover:underline">
                      {exec.txHash}
                    </td>
                    <td className="py-4 px-4 text-body-md">{exec.pair}</td>
                    <td className="py-4 px-4 text-right text-body-md">${exec.gasCost}</td>
                    <td className="py-4 px-4 text-right">
                      <span className={exec.profit > 0 ? 'text-green-600 font-semibold' : 'text-gray-600'}>
                        ${exec.profit}
                      </span>
                    </td>
                    <td className="py-4 px-4 text-center">
                      <span className={`inline-flex items-center px-3 py-1 rounded-full text-label-sm font-semibold ${getStatusBadgeClass(exec.status)}`}>
                        {exec.status}
                      </span>
                    </td>
                    <td className="py-4 px-4 text-right text-label-sm text-on-surface-variant">{exec.timestamp}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </Layout>
  );
};

export default Execution;
