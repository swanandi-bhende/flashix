import React from 'react';
import { HealthStatus } from '@/types';

interface StatusBadgeProps {
  status: HealthStatus;
  label: string;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, label }) => {
  const statusClasses = {
    healthy: 'status-healthy',
    warning: 'status-warning',
    critical: 'status-critical',
  };

  return (
    <span className={`status-badge ${statusClasses[status]}`}>
      <span className={`w-2 h-2 rounded-full`} 
        style={{
          backgroundColor: status === 'healthy' ? '#10b981' : status === 'warning' ? '#f59e0b' : '#ef4444'
        }} 
      />
      {label}
    </span>
  );
};

export default StatusBadge;
