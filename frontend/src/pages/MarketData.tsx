import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, RefreshCw, ChevronRight, AlertTriangle, Link2, Activity, Database } from 'lucide-react';
import { Layout } from '@/components';
import { useDashboardStore } from '@/store';
import StatusBadge from '@/components/StatusBadge';

const statusLabelMap: Record<'healthy' | 'delayed' | 'degraded' | 'offline', 'healthy' | 'warning' | 'critical'> = {
  healthy: 'healthy',
  delayed: 'warning',
  degraded: 'warning',
  offline: 'critical',
};

export const MarketData: React.FC = () => {
  const navigate = useNavigate();
  const marketData = useDashboardStore((s) => s.marketDataCenter);
  const refreshFeeds = useDashboardStore((s) => s.refreshFeeds);

  const [selectedFeedName, setSelectedFeedName] = useState<'Pyth' | 'Chainlink' | 'Fallback'>('Pyth');

  const selectedFeed = marketData.feeds.find((feed) => feed.name === selectedFeedName) ?? marketData.feeds[0];

  const handleRefresh = () => {
    refreshFeeds();
    setSelectedFeedName('Pyth');
  };

  const scrollToSection = (id: string) => {
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  const sourceCards = marketData.feeds.map((feed) => ({
    ...feed,
    staleSafe: feed.stalenessSeconds <= marketData.summary.acceptableFreshnessSeconds,
    priceRange: feed.priceWindowHigh - feed.priceWindowLow,
  }));

  return (
    <Layout>
      <div className="space-y-6">
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate('/')}
              className="p-2 hover:bg-surface-container rounded-lg transition-colors"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div>
              <h1 className="text-display-lg font-serif text-primary">Market Data</h1>
              <p className="text-body-md text-on-surface-variant">Oracle health, freshness, and fallback reliability</p>
            </div>
          </div>
          <div className={`px-4 py-2 rounded-lg text-label-md font-semibold ${marketData.summary.overallStatus === 'healthy' ? 'bg-green-100 text-green-900' : marketData.summary.overallStatus === 'delayed' ? 'bg-yellow-100 text-yellow-900' : 'bg-red-100 text-red-900'}`}>
            {marketData.summary.overallStatus.toUpperCase()}
          </div>
        </div>

        <div className="card border-2 border-primary/20 bg-gradient-to-r from-white to-surface-container">
          <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
            <div>
              <p className="text-label-md text-on-surface-variant uppercase tracking-wider mb-2">Combined Market Data Health</p>
              <h2 className="text-headline-md font-serif mb-2">{marketData.summary.message}</h2>
              <div className="flex flex-wrap gap-4 text-label-md text-on-surface-variant">
                <span>{marketData.summary.healthySources}/{marketData.summary.totalSources} sources healthy</span>
                <span>Freshest price age: {marketData.summary.freshestPriceAgeSeconds}s</span>
                <span>Freshness limit: {marketData.summary.acceptableFreshnessSeconds}s</span>
              </div>
            </div>
            <div className="flex flex-wrap gap-3">
              <button onClick={handleRefresh} className="btn-primary inline-flex items-center gap-2">
                <RefreshCw className="w-4 h-4" />
                Refresh Feeds
              </button>
              <button onClick={() => scrollToSection('feed-breakdown')} className="btn-secondary inline-flex items-center gap-2">
                View Source Breakdown
                <ChevronRight className="w-4 h-4" />
              </button>
              <button onClick={() => scrollToSection('fallback-events')} className="btn-secondary inline-flex items-center gap-2">
                Open Fallback Events
                <AlertTriangle className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="card border-2 border-green-200">
            <p className="text-label-md text-on-surface-variant mb-2">Are the sources healthy?</p>
            <p className="text-display-sm font-serif text-primary">{marketData.summary.healthySources >= 2 ? 'Yes' : 'No'}</p>
            <p className="text-label-sm text-on-surface-variant mt-2">At least two sources should be healthy for execution trust.</p>
          </div>
          <div className="card border-2 border-blue-200">
            <p className="text-label-md text-on-surface-variant mb-2">Is the data fresh?</p>
            <p className="text-display-sm font-serif text-primary">{marketData.summary.freshestPriceAgeSeconds}s</p>
            <p className="text-label-sm text-on-surface-variant mt-2">Acceptable limit: {marketData.summary.acceptableFreshnessSeconds}s</p>
          </div>
          <div className="card border-2 border-purple-200">
            <p className="text-label-md text-on-surface-variant mb-2">Trust for execution?</p>
            <StatusBadge status={marketData.summary.trustForExecution ? 'healthy' : 'critical'} label={marketData.summary.trustForExecution ? 'TRUSTED' : 'UNTRUSTED'} />
            <p className="text-label-sm text-on-surface-variant mt-2">{marketData.summary.trustForExecution ? 'Safe to use for execution checks' : 'Hold execution until the feed recovers'}</p>
          </div>
        </div>

        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-headline-sm font-serif">Oracle Sources</h2>
            <div className="text-label-sm text-on-surface-variant">Latest source status first</div>
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {sourceCards.map((feed) => (
              <article key={feed.id} className={`card border-2 ${feed.status === 'healthy' ? 'border-green-200' : feed.status === 'delayed' ? 'border-yellow-200' : feed.status === 'degraded' ? 'border-orange-200' : 'border-red-200'}`}>
                <div className="flex items-start justify-between gap-3 mb-4">
                  <div>
                    <p className="text-label-md text-on-surface-variant uppercase tracking-wider">{feed.name}</p>
                    <h3 className="text-headline-sm font-serif mt-1">{feed.isLive ? 'Live feed' : 'Offline'}</h3>
                  </div>
                  <StatusBadge status={statusLabelMap[feed.status]} label={feed.status.toUpperCase()} />
                </div>

                <div className="space-y-3 text-body-md">
                  <div className="flex justify-between gap-4">
                    <span className="text-on-surface-variant">Last update</span>
                    <span>{new Date(feed.lastUpdate).toLocaleTimeString()}</span>
                  </div>
                  <div className="flex justify-between gap-4">
                    <span className="text-on-surface-variant">Latest price</span>
                    <span className="font-semibold text-primary">${feed.latestPrice.toLocaleString(undefined, { maximumFractionDigits: 2 })}</span>
                  </div>
                  <div className="flex justify-between gap-4">
                    <span className="text-on-surface-variant">Staleness</span>
                    <span className={feed.stalenessSeconds > marketData.summary.acceptableFreshnessSeconds ? 'text-red-600 font-semibold' : 'text-green-600 font-semibold'}>
                      {feed.stalenessSeconds}s
                    </span>
                  </div>
                  <div className="flex justify-between gap-4">
                    <span className="text-on-surface-variant">Price window</span>
                    <span>${feed.priceWindowLow.toLocaleString(undefined, { maximumFractionDigits: 2 })} - ${feed.priceWindowHigh.toLocaleString(undefined, { maximumFractionDigits: 2 })}</span>
                  </div>
                  {feed.warning && (
                    <div className="p-3 bg-yellow-50 border border-yellow-200 rounded-lg text-label-sm text-yellow-900">
                      {feed.warning}
                    </div>
                  )}
                </div>

                <div className="mt-4 pt-4 border-t border-outline-variant/20 flex items-center justify-between gap-3">
                  <div className="text-label-sm text-on-surface-variant">
                    Window range: ${(feed.priceWindowHigh - feed.priceWindowLow).toLocaleString(undefined, { maximumFractionDigits: 2 })}
                  </div>
                  <button
                    onClick={() => setSelectedFeedName(feed.name)}
                    className="btn-secondary text-sm inline-flex items-center gap-2"
                  >
                    View Source Breakdown
                    <ChevronRight className="w-4 h-4" />
                  </button>
                </div>
              </article>
            ))}
          </div>
        </section>

        <section className="card border-2 border-indigo-200">
          <div className="flex items-center gap-2 mb-4">
            <Database className="w-5 h-5 text-indigo-600" />
            <h2 className="text-headline-sm font-serif">Combined Price Window</h2>
            <span className="text-label-sm text-on-surface-variant">Recent highs, lows, and spread</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <p className="text-label-sm text-on-surface-variant">Window high</p>
              <p className="text-headline-sm font-serif text-primary">${Math.max(...marketData.feeds.map((feed) => feed.priceWindowHigh)).toLocaleString(undefined, { maximumFractionDigits: 2 })}</p>
            </div>
            <div>
              <p className="text-label-sm text-on-surface-variant">Window low</p>
              <p className="text-headline-sm font-serif text-primary">${Math.min(...marketData.feeds.map((feed) => feed.priceWindowLow)).toLocaleString(undefined, { maximumFractionDigits: 2 })}</p>
            </div>
            <div>
              <p className="text-label-sm text-on-surface-variant">Combined spread</p>
              <p className="text-headline-sm font-serif text-primary">
                ${(Math.max(...marketData.feeds.map((feed) => feed.priceWindowHigh)) - Math.min(...marketData.feeds.map((feed) => feed.priceWindowLow))).toLocaleString(undefined, { maximumFractionDigits: 2 })}
              </p>
            </div>
          </div>
          <div className="mt-4 w-full bg-surface-container rounded-full h-2 overflow-hidden">
            <div className="h-2 bg-gradient-to-r from-green-500 via-blue-500 to-purple-500" style={{ width: '100%' }} />
          </div>
        </section>

        <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="card" id="feed-breakdown">
            <div className="flex items-center gap-2 mb-4">
              <Activity className="w-5 h-5 text-primary" />
              <h2 className="text-headline-sm font-serif">Source Breakdown</h2>
            </div>
            <div className="space-y-4">
              <div className="flex items-center gap-3">
                {marketData.feeds.map((feed) => (
                  <button
                    key={feed.id}
                    onClick={() => setSelectedFeedName(feed.name)}
                    className={`px-3 py-2 rounded-full text-sm border transition-colors ${selectedFeed.name === feed.name ? 'bg-primary text-white border-primary' : 'bg-white border-outline-variant text-on-surface-variant hover:bg-surface-container'}`}
                  >
                    {feed.name}
                  </button>
                ))}
              </div>

              <div className="p-4 bg-surface-container rounded-lg border border-outline-variant/20">
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <p className="text-label-md text-on-surface-variant uppercase tracking-wider">{selectedFeed.name} diagnostics</p>
                    <h3 className="text-headline-sm font-serif">Detailed source health</h3>
                  </div>
                  <StatusBadge status={statusLabelMap[selectedFeed.status]} label={selectedFeed.status.toUpperCase()} />
                </div>

                <div className="grid grid-cols-2 gap-4 text-body-md">
                  <div>
                    <p className="text-label-sm text-on-surface-variant">Update frequency</p>
                    <p className="font-semibold mt-1">Every {selectedFeed.updateFrequencySeconds}s</p>
                  </div>
                  <div>
                    <p className="text-label-sm text-on-surface-variant">Failure count</p>
                    <p className={`font-semibold mt-1 ${selectedFeed.failureCount > 0 ? 'text-red-600' : 'text-green-600'}`}>{selectedFeed.failureCount}</p>
                  </div>
                  <div>
                    <p className="text-label-sm text-on-surface-variant">Last successful sample</p>
                    <p className="font-semibold mt-1">{new Date(selectedFeed.lastSuccessfulSample).toLocaleTimeString()}</p>
                  </div>
                  <div>
                    <p className="text-label-sm text-on-surface-variant">Accepted deviation</p>
                    <p className="font-semibold mt-1">{selectedFeed.acceptedDeviationPct}%</p>
                  </div>
                </div>

                {selectedFeed.warning && (
                  <div className="mt-4 p-3 bg-yellow-50 border border-yellow-200 rounded-lg text-label-sm text-yellow-900">
                    {selectedFeed.warning}
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="card" id="fallback-events">
            <div className="flex items-center gap-2 mb-4">
              <Link2 className="w-5 h-5 text-primary" />
              <h2 className="text-headline-sm font-serif">Fallback Events</h2>
            </div>
            <div className="space-y-3">
              {marketData.fallbackEvents.map((event) => (
                <div key={event.id} className="p-4 border border-outline-variant/20 rounded-lg hover:bg-surface-container transition-colors">
                  <div className="flex items-start justify-between gap-3 mb-2">
                    <div>
                      <p className="text-label-md font-semibold">{event.primarySource} {'->'} {event.fallbackSource}</p>
                      <p className="text-label-sm text-on-surface-variant mt-1">{event.triggerReason}</p>
                    </div>
                    <StatusBadge status={event.resolvedAt ? 'healthy' : 'warning'} label={event.resolvedAt ? 'RESOLVED' : 'ACTIVE'} />
                  </div>
                  <div className="grid grid-cols-2 gap-4 text-label-sm text-on-surface-variant">
                    <div>
                      <p>Triggered</p>
                      <p className="font-medium text-on-surface">{new Date(event.triggeredAt).toLocaleString()}</p>
                    </div>
                    <div>
                      <p>Duration</p>
                      <p className="font-medium text-on-surface">{event.durationSeconds ? `${Math.floor(event.durationSeconds / 60)}m ${event.durationSeconds % 60}s` : 'Ongoing'}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="card border-2 border-orange-200">
          <div className="flex items-center gap-2 mb-4">
            <AlertTriangle className="w-5 h-5 text-orange-600" />
            <h2 className="text-headline-sm font-serif">Feed Comparison</h2>
            <span className="text-label-sm text-on-surface-variant">Mismatch detection across sources</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div>
              <p className="text-label-sm text-on-surface-variant">Pyth vs Chainlink</p>
              <p className="text-headline-sm font-serif mt-1">{marketData.comparison.pythVsChainlinkPct.toFixed(2)}%</p>
            </div>
            <div>
              <p className="text-label-sm text-on-surface-variant">Pyth vs Fallback</p>
              <p className="text-headline-sm font-serif mt-1">{marketData.comparison.pythVsFallbackPct.toFixed(2)}%</p>
            </div>
            <div>
              <p className="text-label-sm text-on-surface-variant">Chainlink vs Fallback</p>
              <p className="text-headline-sm font-serif mt-1">{marketData.comparison.chainlinkVsFallbackPct.toFixed(2)}%</p>
            </div>
            <div>
              <p className="text-label-sm text-on-surface-variant">Execution trust</p>
              <StatusBadge status={marketData.comparison.trustForExecution ? 'healthy' : 'critical'} label={marketData.comparison.trustForExecution ? 'TRUSTED' : 'HOLD'} />
            </div>
          </div>
          <div className={`mt-4 p-4 rounded-lg border ${marketData.comparison.hasMaterialMismatch ? 'bg-red-50 border-red-200' : 'bg-green-50 border-green-200'}`}>
            <p className={`text-label-md font-semibold ${marketData.comparison.hasMaterialMismatch ? 'text-red-900' : 'text-green-900'}`}>
              {marketData.comparison.hasMaterialMismatch
                ? 'Material mismatch detected across oracle sources. Investigate before allowing trades to proceed.'
                : 'No material mismatch detected. Sources remain aligned within execution tolerance.'}
            </p>
          </div>
        </section>
      </div>
    </Layout>
  );
};

export default MarketData;
