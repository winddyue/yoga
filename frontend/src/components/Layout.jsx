import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth';

// 顶部导航 + 侧边菜单（极简）：按角色显示不同入口
const ROLE_NAME = { owner: '馆主', coach: '教练', client: '客户' };

export default function Layout({ children }) {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  if (!user) { nav('/login'); return null; }
  const role = user.role;
  const items = role === 'client'
    ? [['/', '我的进展'], ['/courses', '约课']]
    : [
        ['/', role === 'owner' ? '经营概况' : '工作台'],
        ['/clients', '客户'],
        ['/courses', '约课签到'],
        ['/intake', '智能录入'],
        ...(role === 'owner'
          ? [['/users', '账号管理'], ['/fields', '自定义字段'], ['/settings', '设置']]
          : []),
      ];
  return (
    <div className="min-h-screen flex">
      <aside className="w-44 bg-white border-r border-sand p-4 space-y-1 shrink-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="w-2.5 h-2.5 rounded-full bg-brand-400"></span>
          <span className="font-bold text-brand-700 tracking-widest text-sm">客户管理</span>
        </div>
        <div className="text-xs text-clay mb-4">{user.name || user.username}（{ROLE_NAME[role] || role}）</div>
        {items.map(([to, label]) => (
          <Link key={to} to={to} className="block px-4 py-2 rounded-full text-sm text-muted hover:bg-brand-50 hover:text-brand-700 transition">{label}</Link>
        ))}
        <button onClick={logout} className="block w-full text-left px-4 py-2 rounded-full text-sm text-[#B4655F] hover:bg-[#FBF0EE] transition">退出</button>
      </aside>
      <main className="flex-1 p-6 max-w-5xl">{children}</main>
    </div>
  );
}
