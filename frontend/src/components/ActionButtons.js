import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useNavigate } from 'react-router-dom';
export const ActionButtons = ({ actions }) => {
    const navigate = useNavigate();
    return (_jsx("div", { className: "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7 gap-4", children: actions.map(({ id, label, icon: Icon, path }) => (_jsxs("button", { onClick: () => navigate(path), className: "btn-primary flex flex-col items-center justify-center gap-2 py-4 min-h-[100px] group", children: [_jsx(Icon, { className: "w-6 h-6 group-hover:scale-110 transition-transform" }), _jsx("span", { className: "text-label-md text-center", children: label })] }, id))) }));
};
export default ActionButtons;
//# sourceMappingURL=ActionButtons.js.map