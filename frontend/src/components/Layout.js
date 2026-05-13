import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import Header from './Header';
export const Layout = ({ children, onRefresh, isLoading }) => {
    return (_jsxs("div", { className: "min-h-screen bg-surface", children: [_jsx(Header, { onRefresh: onRefresh, isLoading: isLoading }), _jsx("main", { className: "container-padding py-8", children: children })] }));
};
export default Layout;
//# sourceMappingURL=Layout.js.map