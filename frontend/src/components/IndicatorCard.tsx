import React from 'react';
import { LucideIcon } from 'lucide-react';
import { HealthStatus } from '@/types';
import StatusBadge from './StatusBadge';

interface IndicatorCardProps {
  title: string;
  value: string | number;
  status: HealthStatus;
  statusLabel: string;
  description: string;
  icon: LucideIcon;
  onClick: () => void;
  trend?: {
    value: number;
    direction: 'up' | 'down';
  };
}

export const IndicatorCard: React.FC<IndicatorCardProps> = ({
  title,
  value,
  status,
  statusLabel,
  description,
  icon: Icon,
  onClick,
  trend,
}) => {
  return (
    <div
      onClick={onClick}
      className="card cursor-pointer hover:shadow-elevation-2 transition-all hover:translate-y-[-2px] group"
    >
      <div className="flex items-start justify-between mb-4">
        <div>
          <h3 className="text-label-md font-semibold text-on-surface mb-1">{title}</h3>
          <p className="text-body-md font-serif text-primary group-hover:text-primary/80 transition-colors">
            {value}
          </p>
        </div>
        <div className="p-3 bg-primary/10 rounded-lg group-hover:bg-primary/15 transition-colors">
          <Icon className="w-6 h-6 text-primary" />
        </div>
      </div>

      <div className="space-y-2">
        <StatusBadge status={status} label={statusLabel} />
          <p className="text-body-md text-on-surface-variant">
          {description}
        </p>
        {trend && (
          <div className="flex items-center gap-1 text-label-sm">
            <span className={trend.direction === 'up' ? 'text-green-600' : 'text-red-600'}>
              {trend.direction === 'up' ? '↑' : '↓'} {Math.abs(trend.value)}
            </span>
            <span className="text-on-surface-variant">from last hour</span>
          </div>
        )}
      </div>
    </div>
  );
};

export default IndicatorCard;
