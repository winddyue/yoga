import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '../api';
import { useAuth } from '../auth';

// 顶部导航 + 侧边菜单（极简）：按角色显示不同入口
const ROLE_NAME = { owner: '馆主', coach: '教练', client: '客户' };

// 通知铃铛：未读 badge + 下拉面板，30 秒轮询一次
function NotifyBell() {
  const [unread, setUnread] = useState(0);
  const [open, setOpen] = useState(false);
  const [list, setList] = useState([]);
  const boxRef = useRef(null);
  const fetchUnread = () => api.get('/api/notifications/unread-count')
    .then((r) => setUnread(r.unread || 0)).catch(() => {});
  useEffect(() => {
    fetchUnread();
    const t = setInterval(fetchUnread, 30000);
    return () => clearInterval(t);
  }, []);
  useEffect(() => {
    const close = (e) => { if (boxRef.current && !boxRef.current.contains(e.target)) setOpen(false); };
    document.addEventListener('click', close);
    return () => document.removeEventListener('click', close);
  }, []);
  const toggle = async () => {
    const next = !open;
    setOpen(next);
    if (next) {
      try { setList(await api.get('/api/notifications?limit=15')); }
      catch (e) { /* 已有全局错误处理 */ }
    }
  };
  const markOne = async (id) => {
    await api.post(`/api/notifications/${id}/read`).catch(() => {});
    setList((l) => l.map((n) => (n.id === id ? { ...n, is_read: true } : n)));
    setUnread((u) => Math.max(0, u - 1));
  };
  const markAll = async () => {
    await api.post('/api/notifications/read-all').catch(() => {});
    setList((l) => l.map((n) => ({ ...n, is_read: true })));
    setUnread(0);
  };
  return (
    <div ref={boxRef} className="relative">
      <button onClick={toggle} className="relative text-xl px-2 py-1 rounded-full hover:bg-brand-50 transition" title="通知">
        🔔
        {unread > 0 && (
          <span className="absolute -top-0.5 -right-0.5 min-w-[18px] h-[18px] px-1 rounded-full bg-[#C0392B] text-white text-[10px] flex items-center justify-center font-bold">
            {unread > 99 ? '99+' : unread}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 mt-2 w-80 max-h-96 overflow-auto card !p-0 z-50 shadow-lg">
          <div className="flex justify-between items-center px-4 py-2 border-b border-sand">
            <span className="font-bold text-sm">通知</span>
            <button onClick={markAll} className="text-xs text-brand-600 hover:underline">全部已读</button>
          </div>
          {list.length === 0 && <div className="px-4 py-6 text-sm text-clay text-center">暂无通知</div>}
          {list.map((n) => (
            <div key={n.id} onClick={() => markOne(n.id)}
                 className={`px-4 py-2.5 border-b border-sand cursor-pointer hover:bg-cream transition ${n.is_read ? 'opacity-60' : ''}`}>
              <div className="text-sm font-medium flex items-center gap-1.5">
                {!n.is_read && <span className="w-1.5 h-1.5 rounded-full bg-[#C0392B] shrink-0"></span>}
                {n.title}
              </div>
              <div className="text-xs text-muted mt-0.5">{n.body}</div>
              <div className="text-[10px] text-clay mt-1">{(n.created_at || '').slice(0, 16).replace('T', ' ')}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

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
        <div className="flex items-center justify-between mb-1">
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-brand-400"></span>
            <span className="font-bold text-brand-700 tracking-widest text-sm">客户管理</span>
          </div>
          <NotifyBell />
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
