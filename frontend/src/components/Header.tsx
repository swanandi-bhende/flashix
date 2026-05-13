import React from 'react';
import { useNavigate } from 'react-router-dom';
import { RefreshCw } from 'lucide-react';

interface HeaderProps {
  onRefresh?: () => void;
  isLoading?: boolean;
}

export const Header: React.FC<HeaderProps> = ({ onRefresh, isLoading = false }) => {
  const navigate = useNavigate();

  return (
    <header className="sticky top-0 z-40 bg-white border-b border-outline-variant/20 shadow-elevation-1">
      <div className="container-padding py-4">
        <div className="flex items-center justify-between">
          <div 
            className="cursor-pointer hover:opacity-80 transition-opacity"
            onClick={() => navigate('/')}
          >
            <h1 className="text-headline-md font-serif text-primary">
              Flashix
            </h1>
            <p className="text-label-sm text-on-surface-variant">Arbitrage Dashboard</p>
          </div>

          <button
            onClick={onRefresh}
            disabled={isLoading}
            className={`p-2 rounded-lg bg-primary/10 hover:bg-primary/20 transition-colors ${
              isLoading ? 'animate-spin' : ''
            }`}
          >
            <RefreshCw className="w-5 h-5 text-primary" />
          </button>
        </div>
      </div>
    </header>
  );
};

export default Header;
