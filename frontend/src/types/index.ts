// System health statuses
export type HealthStatus = 'healthy' | 'warning' | 'critical';

// Pipeline states
export type PipelineState = 'idle' | 'processing' | 'degraded' | 'halted';

// Risk states
export type RiskStatus = 'green' | 'elevated' | 'blocked';

// Core system metrics
export interface SystemMetrics {
  pipelineState: PipelineState;
  totalOpportunities: number;
  activeOpportunities: number;
  livePositions: number;
  riskStatus: RiskStatus;
  openBreakers: number;
  executionHealth: HealthStatus;
  recentExecutions: number;
  settlementStatus: HealthStatus;
  marketDataFreshness: number; // age in seconds
  lastMarketDataSample: Date;
}

// Activity event types
export type ActivityEventType = 
  | 'opportunity_detected' 
  | 'risk_event' 
  | 'execution' 
  | 'settlement' 
  | 'market_feed';

export interface ActivityEvent {
  id: string;
  type: ActivityEventType;
  timestamp: Date;
  title: string;
  description: string;
  status: HealthStatus;
  details?: Record<string, any>;
}

// Pipeline monitoring
export interface PipelineStatus {
  state: PipelineState;
  activeWorkers: number;
  totalWorkers: number;
  processedToday: number;
  failedToday: number;
  avgLatency: number;
}

// Opportunity
export interface Opportunity {
  id: string;
  detectionTime: Date;
  source: string;
  type: string;
  expectedProfit: number;
  risk: number;
  status: 'pending' | 'executing' | 'completed' | 'failed';
}

// Risk event
export interface RiskEvent {
  id: string;
  timestamp: Date;
  severity: 'low' | 'medium' | 'high' | 'critical';
  category: string;
  description: string;
  breaker?: string;
}

// Execution record
export interface ExecutionRecord {
  id: string;
  opportunityId: string;
  timestamp: Date;
  status: 'pending' | 'confirmed' | 'failed';
  gasCost: number;
  profit: number;
  txHash?: string;
}

// Settlement status
export interface SettlementStatus {
  pendingRepayments: number;
  completedToday: number;
  failedToday: number;
  lastSettlementTime: Date;
  ledgerBalance: number;
}

// Market data feed
export interface MarketDataFeed {
  name: string;
  lastUpdate: Date;
  isHealthy: boolean;
  samples: number;
}
