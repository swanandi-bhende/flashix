import React from 'react';
import { useNavigate } from 'react-router-dom';
import { LucideIcon } from 'lucide-react';

interface ActionButtonsProps {
  actions: Array<{
    id: string;
    label: string;
    icon: LucideIcon;
    path: string;
  }>;
}

export const ActionButtons: React.FC<ActionButtonsProps> = ({ actions }) => {
  const navigate = useNavigate();

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7 gap-4">
      {actions.map(({ id, label, icon: Icon, path }) => (
        <button
          key={id}
          onClick={() => navigate(path)}
          className="btn-primary flex flex-col items-center justify-center gap-2 py-4 min-h-[100px] group"
        >
          <Icon className="w-6 h-6 group-hover:scale-110 transition-transform" />
          <span className="text-label-md text-center">{label}</span>
        </button>
      ))}
    </div>
  );
};

export default ActionButtons;
