import React, { ReactNode } from 'react';
import Header from './Header';

interface LayoutProps {
  children: ReactNode;
  onRefresh?: () => void;
  isLoading?: boolean;
}

export const Layout: React.FC<LayoutProps> = ({ children, onRefresh, isLoading }) => {
  return (
    <div className="min-h-screen bg-surface">
      <Header onRefresh={onRefresh} isLoading={isLoading} />
      <main className="container-padding py-8">
        {children}
      </main>
    </div>
  );
};

export default Layout;
