import { createBrowserRouter } from 'react-router-dom';
import {
  Dashboard,
  Pipeline,
  Opportunities,
  OpportunityDetail,
  Risk,
  Execution,
  Settlement,
  MarketData,
  Compute,
  Admin,
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
    path: '/opportunity/:id',
    element: <OpportunityDetail />,
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
  {
    path: '/compute',
    element: <Compute />,
  },
  {
    path: '/admin',
    element: <Admin />,
  },
]);
