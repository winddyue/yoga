import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth';

// 顶部导航 + 侧边菜单（极简）：按角色显示不同入口
export default function Layout({ children }) {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  if (!user) { nav('/login'); return null; }
  const owner = user.role === 'owner';
  const items = [
    ['/', '总览'],
    ['/clients', '客户'],
    ...(owner ? [['/users', '教练账号'], ['/fields', '自定义字段'], ['/settings', '设置']] : []),
  ];
  return (
    <div className="min-h-screen flex">
      <aside className="w-44 bg-white border-r p-4 space-y-1 shrink-0">
        <div className="font-bold text-teal-700 mb-1">客户管理</div>
        <div className="text-xs text-gray-400 mb-4">{user.name || user.username}（{owner ? '馆主' : '教练'}）</div>
        {items.map(([to, label]) => (
          <Link key={to} to={to} className="block px-3 py-2 rounded hover:bg-teal-50 text-sm">{label}</Link>
        ))}
        <button onClick={logout} className="block w-full text-left px-3 py-2 rounded hover:bg-red-50 text-sm text-red-600">退出</button>
      </aside>
      <main className="flex-1 p-6 max-w-5xl">{children}</main>
    </div>
  );
}
