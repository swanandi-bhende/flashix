import React from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { Layout } from '@/components';
import { StatusBadge } from '@/components';

export const Risk: React.FC = () => {
  const navigate = useNavigate();

  const riskEvents = [
    {
      id: '1',
      severity: 'high' as const,
      category: 'Slippage',
      description: 'ETH/USDC slippage exceeded 0.5%',
      timestamp: '5 minutes ago',
    },
    {
      id: '2',
      severity: 'medium' as const,
      category: 'Liquidity',
      description: 'Trading pair volume dropped 30%',
      timestamp: '12 minutes ago',
    },
    {
      id: '3',
      severity: 'low' as const,
      category: 'Latency',
      description: 'Market feed delay detected',
      timestamp: '25 minutes ago',
    },
  ];

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'high':
      case 'critical':
        return 'bg-error-container text-on-error-container';
      case 'medium':
        return 'bg-yellow-100 text-yellow-900';
      case 'low':
        return 'bg-blue-100 text-blue-900';
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
            <h1 className="text-display-lg font-serif text-primary">Risk Center</h1>
            <p className="text-body-md text-on-surface-variant">
              Monitor risk events, breakers, and system safety limits
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <div className="card">
            <p className="text-label-md text-on-surface-variant mb-2">Overall Risk Status</p>
            <StatusBadge status="warning" label="ELEVATED" />
            <p className="text-label-sm text-on-surface-variant mt-2">Minor events detected</p>
          </div>
          <div className="card">
            <p className="text-label-md text-on-surface-variant mb-2">Active Breakers</p>
            <p className="text-headline-md font-serif text-error">2</p>
            <p className="text-label-sm text-on-surface-variant mt-2">Slippage, Liquidity</p>
          </div>
          <div className="card">
            <p className="text-label-md text-on-surface-variant mb-2">Triggered Today</p>
            <p className="text-headline-md font-serif text-primary">5</p>
            <p className="text-label-sm text-on-surface-variant mt-2">All resolved</p>
          </div>
        </div>

        <div className="card">
          <h2 className="text-headline-sm font-serif mb-6">Recent Risk Events</h2>
          <div className="space-y-4">
            {riskEvents.map((event) => (
              <div
                key={event.id}
                className={`p-4 rounded-lg border border-outline-variant/30 ${getSeverityColor(event.severity)}`}
              >
                <div className="flex justify-between items-start mb-2">
                  <div>
                    <p className="text-label-md font-semibold">{event.category}</p>
                    <p className="text-label-sm opacity-80 mt-1">{event.description}</p>
                  </div>
                  <span className="text-label-sm font-semibold uppercase">{event.severity}</span>
                </div>
                <p className="text-label-sm opacity-60">{event.timestamp}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="card">
          <h2 className="text-headline-sm font-serif mb-6">Risk Configuration</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <p className="text-label-md text-on-surface-variant mb-2">Max Slippage</p>
              <p className="text-headline-md font-serif text-primary">0.5%</p>
              <p className="text-label-sm text-on-surface-variant mt-1">Current: 0.48%</p>
            </div>
            <div>
              <p className="text-label-md text-on-surface-variant mb-2">Min Liquidity</p>
              <p className="text-headline-md font-serif text-primary">$500K</p>
              <p className="text-label-sm text-on-surface-variant mt-1">Current: $1.2M</p>
            </div>
            <div>
              <p className="text-label-md text-on-surface-variant mb-2">Max Position Size</p>
              <p className="text-headline-md font-serif text-primary">$1M</p>
              <p className="text-label-sm text-on-surface-variant mt-1">Current: $450K</p>
            </div>
            <div>
              <p className="text-label-md text-on-surface-variant mb-2">Max Daily Loss</p>
              <p className="text-headline-md font-serif text-primary">$50K</p>
              <p className="text-label-sm text-on-surface-variant mt-1">Current: -$12K</p>
            </div>
          </div>
        </div>
      </div>
    </Layout>
  );
};

export default Risk;
