import React from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { Layout } from '@/components';
import { StatusBadge } from '@/components';

export const Settlement: React.FC = () => {
  const navigate = useNavigate();

  const settlements = [
    {
      id: '1',
      tradeId: 'TRADE-001',
      amount: 45000,
      status: 'completed',
      timestamp: '1 hour ago',
    },
    {
      id: '2',
      tradeId: 'TRADE-002',
      amount: 38500,
      status: 'completed',
      timestamp: '2 hours ago',
    },
    {
      id: '3',
      tradeId: 'TRADE-003',
      amount: 52000,
      status: 'pending',
      timestamp: '15 minutes ago',
    },
  ];

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
            <h1 className="text-display-lg font-serif text-primary">Settlement Center</h1>
            <p className="text-body-md text-on-surface-variant">
              Monitor position repayment, ledger entries, and trade outcomes
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <div className="card">
            <p className="text-label-md text-on-surface-variant mb-2">Settlement Status</p>
            <StatusBadge status="healthy" label="HEALTHY" />
            <p className="text-label-sm text-on-surface-variant mt-2">All on schedule</p>
          </div>
          <div className="card">
            <p className="text-label-md text-on-surface-variant mb-2">Completed Today</p>
            <p className="text-headline-md font-serif text-primary">34</p>
            <p className="text-label-sm text-on-surface-variant mt-2">$1.2M settled</p>
          </div>
          <div className="card">
            <p className="text-label-md text-on-surface-variant mb-2">Ledger Balance</p>
            <p className="text-headline-md font-serif text-primary">$450K</p>
            <p className="text-label-sm text-on-surface-variant mt-2">Available funds</p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="card">
            <h2 className="text-headline-sm font-serif mb-4">Repayment Status</h2>
            <div className="space-y-4">
              <div>
                <div className="flex justify-between mb-2">
                  <span className="text-body-md">Pending Repayments</span>
                  <span className="font-semibold text-primary">5</span>
                </div>
                <div className="w-full bg-surface-container rounded-full h-2">
                  <div className="bg-yellow-500 h-2 rounded-full" style={{ width: '100%' }}></div>
                </div>
              </div>
              <div>
                <div className="flex justify-between mb-2">
                  <span className="text-body-md">Total Amount</span>
                  <span className="font-semibold text-primary">$125K</span>
                </div>
                <p className="text-label-sm text-on-surface-variant">
                  Expected completion in 4 hours
                </p>
              </div>
            </div>
          </div>

          <div className="card">
            <h2 className="text-headline-sm font-serif mb-4">Ledger Summary</h2>
            <div className="space-y-3">
              <div className="flex justify-between">
                <span className="text-body-md">Total Deposits</span>
                <span className="font-semibold text-primary">$5.2M</span>
              </div>
              <div className="flex justify-between">
                <span className="text-body-md">Total Withdrawals</span>
                <span className="font-semibold text-primary">$4.75M</span>
              </div>
              <div className="divider"></div>
              <div className="flex justify-between">
                <span className="font-semibold text-body-md">Net Balance</span>
                <span className="font-semibold text-primary">$450K</span>
              </div>
            </div>
          </div>
        </div>

        <div className="card">
          <h2 className="text-headline-sm font-serif mb-6">Recent Settlement Transactions</h2>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-outline-variant/30">
                  <th className="text-left py-3 px-4 text-label-md text-on-surface-variant">Trade ID</th>
                  <th className="text-right py-3 px-4 text-label-md text-on-surface-variant">Amount</th>
                  <th className="text-center py-3 px-4 text-label-md text-on-surface-variant">Status</th>
                  <th className="text-right py-3 px-4 text-label-md text-on-surface-variant">Time</th>
                </tr>
              </thead>
              <tbody>
                {settlements.map((settlement) => (
                  <tr key={settlement.id} className="border-b border-outline-variant/20 hover:bg-surface-container transition-colors">
                    <td className="py-4 px-4 text-body-md text-on-surface">{settlement.tradeId}</td>
                    <td className="py-4 px-4 text-right text-body-md font-semibold">
                      ${settlement.amount.toLocaleString()}
                    </td>
                    <td className="py-4 px-4 text-center">
                      <span
                        className={`inline-flex items-center px-3 py-1 rounded-full text-label-sm font-semibold ${
                          settlement.status === 'completed'
                            ? 'bg-green-100 text-green-900'
                            : 'bg-yellow-100 text-yellow-900'
                        }`}
                      >
                        {settlement.status}
                      </span>
                    </td>
                    <td className="py-4 px-4 text-right text-label-sm text-on-surface-variant">
                      {settlement.timestamp}
                    </td>
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

export default Settlement;
