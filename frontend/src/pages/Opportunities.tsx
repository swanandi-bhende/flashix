import React from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { Layout } from '@/components';

export const Opportunities: React.FC = () => {
  const navigate = useNavigate();

  const mockOpportunities = [
    {
      id: '1',
      pair: 'ETH/USDC',
      expectedProfit: 2450,
      risk: 0.45,
      status: 'executing',
      detectedAt: '2 minutes ago',
    },
    {
      id: '2',
      pair: 'DAI/USDC',
      expectedProfit: 1850,
      risk: 0.32,
      status: 'pending',
      detectedAt: '5 minutes ago',
    },
    {
      id: '3',
      pair: 'WBTC/BTC',
      expectedProfit: 3200,
      risk: 0.68,
      status: 'pending',
      detectedAt: '12 minutes ago',
    },
  ];

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'executing':
        return 'bg-blue-100 text-blue-900';
      case 'pending':
        return 'bg-yellow-100 text-yellow-900';
      case 'completed':
        return 'bg-green-100 text-green-900';
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
            <h1 className="text-display-lg font-serif text-primary">Opportunities Queue</h1>
            <p className="text-body-md text-on-surface-variant">
              All detected arbitrage opportunities with profit expectations
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <div className="card">
            <p className="text-label-md text-on-surface-variant mb-2">Total Detected</p>
            <p className="text-headline-md font-serif text-primary">247</p>
          </div>
          <div className="card">
            <p className="text-label-md text-on-surface-variant mb-2">Currently Active</p>
            <p className="text-headline-md font-serif text-primary">12</p>
          </div>
          <div className="card">
            <p className="text-label-md text-on-surface-variant mb-2">Pending Execution</p>
            <p className="text-headline-md font-serif text-primary">8</p>
          </div>
        </div>

        <div className="card">
          <h2 className="text-headline-sm font-serif mb-6">Active Opportunities</h2>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-outline-variant/30">
                  <th className="text-left py-3 px-4 text-label-md text-on-surface-variant">Pair</th>
                  <th className="text-right py-3 px-4 text-label-md text-on-surface-variant">Expected Profit</th>
                  <th className="text-right py-3 px-4 text-label-md text-on-surface-variant">Risk %</th>
                  <th className="text-center py-3 px-4 text-label-md text-on-surface-variant">Status</th>
                  <th className="text-right py-3 px-4 text-label-md text-on-surface-variant">Detected</th>
                </tr>
              </thead>
              <tbody>
                {mockOpportunities.map((opp) => (
                  <tr key={opp.id} className="border-b border-outline-variant/20 hover:bg-surface-container transition-colors">
                    <td className="py-4 px-4 text-body-md text-on-surface">{opp.pair}</td>
                    <td className="py-4 px-4 text-right">
                      <span className="text-body-md text-primary">${opp.expectedProfit}</span>
                    </td>
                    <td className="py-4 px-4 text-right text-body-md">{opp.risk}%</td>
                    <td className="py-4 px-4 text-center">
                      <span className={`inline-flex items-center px-3 py-1 rounded-full text-label-sm font-semibold ${getStatusColor(opp.status)}`}>
                        {opp.status}
                      </span>
                    </td>
                    <td className="py-4 px-4 text-right text-label-sm text-on-surface-variant">{opp.detectedAt}</td>
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

export default Opportunities;
