import { createBrowserRouter } from 'react-router-dom';
import {
  Dashboard,
  Pipeline,
  Opportunities,
  Risk,
  Execution,
  Settlement,
  MarketData,
} from '@/pages';

export const router = createBrowserRouter([
  {
    path: '/',
    element: <Dashboard />,
  },
  {
    path: '/pipeline',
    element: <Pipeline />,
  },
  {
    path: '/pipeline/:stage',
    element: <Pipeline />,
  },
  {
    path: '/opportunities',
    element: <Opportunities />,
  },
  {
    path: '/risk',
    element: <Risk />,
  },
  {
    path: '/execution',
    element: <Execution />,
  },
  {
    path: '/settlement',
    element: <Settlement />,
  },
  {
    path: '/market-data',
    element: <MarketData />,
  },
]);
