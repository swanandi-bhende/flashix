import React from 'react';
import { LucideIcon } from 'lucide-react';
import { HealthStatus } from '@/types';
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
export declare const IndicatorCard: React.FC<IndicatorCardProps>;
export default IndicatorCard;
//# sourceMappingURL=IndicatorCard.d.ts.map