import React from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { Layout } from '@/components';
import { StatusBadge } from '@/components';

export const MarketData: React.FC = () => {
  const navigate = useNavigate();

  const feeds = [
    {
      id: '1',
      name: 'Uniswap V3 USDC Swap',
      status: 'healthy',
      lastUpdate: '2 seconds ago',
      samples: 45000,
    },
    {
      id: '2',
      name: 'Curve 3CRV Pool',
      status: 'healthy',
      lastUpdate: '5 seconds ago',
      samples: 32000,
    },
    {
      id: '3',
      name: 'Balancer Weighted Pool',
      status: 'warning',
      lastUpdate: '45 seconds ago',
      samples: 18000,
    },
    {
      id: '4',
      name: 'AAVE LendingPool',
      status: 'healthy',
      lastUpdate: '3 seconds ago',
      samples: 22500,
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
            <h1 className="text-display-lg font-serif text-primary">Market Data Feeds</h1>
            <p className="text-body-md text-on-surface-variant">
              Monitor real-time price feeds, latency, and data quality
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <div className="card">
            <p className="text-label-md text-on-surface-variant mb-2">Overall Health</p>
            <StatusBadge status="healthy" label="HEALTHY" />
            <p className="text-label-sm text-on-surface-variant mt-2">All feeds operational</p>
          </div>
          <div className="card">
            <p className="text-label-md text-on-surface-variant mb-2">Active Feeds</p>
            <p className="text-headline-md font-serif text-primary">4/4</p>
            <p className="text-label-sm text-on-surface-variant mt-2">100% uptime</p>
          </div>
          <div className="card">
            <p className="text-label-md text-on-surface-variant mb-2">Total Samples</p>
            <p className="text-headline-md font-serif text-primary">117.5K</p>
            <p className="text-label-sm text-on-surface-variant mt-2">Last 24 hours</p>
          </div>
        </div>

        <div className="card">
          <h2 className="text-headline-sm font-serif mb-6">Price Feeds</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {feeds.map((feed) => (
              <div
                key={feed.id}
                className="p-4 border border-outline-variant/20 rounded-lg hover:shadow-elevation-1 transition-all"
              >
                <div className="flex justify-between items-start mb-3">
                  <div>
                    <h3 className="text-body-md text-on-surface">{feed.name}</h3>
                  </div>
                  <StatusBadge status={feed.status === 'healthy' ? 'healthy' : 'warning'} label={feed.status} />
                </div>

                <div className="space-y-2 text-label-sm">
                  <div className="flex justify-between">
                    <span className="text-on-surface-variant">Last Update</span>
                    <span className="text-on-surface">{feed.lastUpdate}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-on-surface-variant">Samples</span>
                    <span className="text-on-surface">{feed.samples.toLocaleString()}</span>
                  </div>
                </div>

                <div className="mt-3 pt-3 border-t border-outline-variant/20">
                  <div className="w-full bg-surface-container rounded-full h-2">
                    <div
                      className="bg-primary h-2 rounded-full"
                      style={{ width: feed.status === 'healthy' ? '100%' : '70%' }}
                    ></div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="card">
            <h2 className="text-headline-sm font-serif mb-4">Feed Latency</h2>
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-body-md">Avg Latency</span>
                <span className="text-headline-md font-serif text-primary">125ms</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-body-md">P95 Latency</span>
                <span className="text-headline-md font-serif text-primary">340ms</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-body-md">Max Latency</span>
                <span className="text-headline-md font-serif text-primary">890ms</span>
              </div>
              <p className="text-label-sm text-on-surface-variant">Within acceptable thresholds</p>
            </div>
          </div>

          <div className="card">
            <h2 className="text-headline-sm font-serif mb-4">Data Quality</h2>
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-body-md">Missing Updates</span>
                <span className="text-headline-md font-serif text-green-600">0</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-body-md">Stale Data</span>
                <span className="text-headline-md font-serif text-green-600">0</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-body-md">Quality Score</span>
                <span className="text-headline-md font-serif text-primary">99.9%</span>
              </div>
              <p className="text-label-sm text-on-surface-variant">Excellent data consistency</p>
            </div>
          </div>
        </div>
      </div>
    </Layout>
  );
};

export default MarketData;
