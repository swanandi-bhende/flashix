import { jsx as _jsx } from "react/jsx-runtime";
import { createBrowserRouter } from 'react-router-dom';
import { Dashboard, Pipeline, Opportunities, Risk, Execution, Settlement, MarketData, } from '@/pages';
export const router = createBrowserRouter([
    {
        path: '/',
        element: _jsx(Dashboard, {}),
    },
    {
        path: '/pipeline',
        element: _jsx(Pipeline, {}),
    },
    {
        path: '/pipeline/:stage',
        element: _jsx(Pipeline, {}),
    },
    {
        path: '/opportunities',
        element: _jsx(Opportunities, {}),
    },
    {
        path: '/risk',
        element: _jsx(Risk, {}),
    },
    {
        path: '/execution',
        element: _jsx(Execution, {}),
    },
    {
        path: '/settlement',
        element: _jsx(Settlement, {}),
    },
    {
        path: '/market-data',
        element: _jsx(MarketData, {}),
    },
]);
//# sourceMappingURL=router.js.map