import React from 'react';
import { Circle, AlertTriangle, MoveRight, ShieldCheck, Workflow, type LucideIcon } from 'lucide-react';
import { ActivityEvent } from '@/types';
import StatusBadge from './StatusBadge';

interface ActivityFeedProps {
  activities: ActivityEvent[];
  maxItems?: number;
}

const getActivityIcon = (type: ActivityEvent['type']): LucideIcon => {
  const icons: Record<ActivityEvent['type'], LucideIcon> = {
    opportunity_detected: MoveRight,
    risk_event: AlertTriangle,
    execution: Workflow,
    settlement: ShieldCheck,
    market_feed: Circle,
  };

  return icons[type];
};

const getActivityTypeLabel = (type: ActivityEvent['type']): string => {
  const labels = {
    opportunity_detected: 'Opportunity',
    risk_event: 'Risk Event',
    execution: 'Execution',
    settlement: 'Settlement',
    market_feed: 'Market Data',
  };
  return labels[type];
};

export const ActivityFeed: React.FC<ActivityFeedProps> = ({ activities, maxItems = 8 }) => {
  const displayedActivities = activities.slice(0, maxItems);

  const formatTime = (date: Date) => {
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);

    if (minutes < 1) return 'Just now';
    if (minutes < 60) return `${minutes}m ago`;
    if (hours < 24) return `${hours}h ago`;
    return date.toLocaleDateString();
  };

  return (
    <div className="card">
      <h2 className="text-headline-sm font-serif mb-6">Recent Activity</h2>
      <div className="space-y-4">
        {displayedActivities.map((activity, index) => (
          <div key={activity.id}>
            <div className="flex gap-4">
              <div className="p-2 rounded-full bg-surface-container-low flex-shrink-0 text-primary">
                {React.createElement(getActivityIcon(activity.type), { className: 'w-5 h-5' })}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-start justify-between gap-2 mb-1">
                  <div>
                    <p className="text-label-md text-on-surface">{activity.title}</p>
                    <p className="text-label-sm text-on-surface-variant">
                      {getActivityTypeLabel(activity.type)} · {formatTime(activity.timestamp)}
                    </p>
                  </div>
                  <StatusBadge status={activity.status} label={activity.status} />
                </div>
                <p className="text-body-md text-on-surface-variant">{activity.description}</p>
              </div>
            </div>
            {index < displayedActivities.length - 1 && <div className="divider my-4" />}
          </div>
        ))}
      </div>
    </div>
  );
};

export default ActivityFeed;
