import { useEffect, useState } from 'react';
import { api } from '../api';
import { useAuth } from '../auth';
import Layout from '../components/Layout';

const LIGHT = { red: '🔴', yellow: '🟡', green: '🟢' };

// 总览页：按角色展示不同汇总
export default function Dashboard() {
  const { user } = useAuth();
  const [d, setD] = useState(null);
  useEffect(() => {
    const url = user.role === 'client' ? '/api/dashboard/me/summary'
      : user.role === 'owner' ? '/api/dashboard/owner/overview'
      : '/api/dashboard/coach/overview';
    api.get(url).then(setD).catch(console.error);
  }, [user.role]);
  if (!d) return <Layout><div>加载中…</div></Layout>;

  if (user.role === 'client') return (
    <Layout>
      <h1 className="text-xl font-bold mb-4">我的进展</h1>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[['目标', d.goal], ['出勤率', `${Math.round((d.attendance_rate || 0) * 100)}%`],
          ['体重变化', `${d.weight_change > 0 ? '+' : ''}${d.weight_change}kg`],
          ['饮食方案已确认', d.diet_confirmed]].map(([k, v]) => (
          <div key={k} className="card text-center">
            <div className="text-2xl font-bold text-teal-700">{v}</div>
            <div className="text-sm text-gray-500 mt-1">{k}</div>
          </div>
        ))}
      </div>
      <div className="card mt-4 text-sm">当前状态 {LIGHT[d.status] || ''} · 待上课程 {d.upcoming_bookings} 节</div>
    </Layout>
  );

  if (user.role === 'owner') return (
    <Layout>
      <h1 className="text-xl font-bold mb-4">经营概况</h1>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[['总客户', d.total_clients], ['近30天新增', d.new_clients_30d],
          ['近30天活跃', d.active_clients_30d], ['课程数', d.course_count],
          ['近30天预约', d.bookings_30d], ['累计签到', d.total_checkins],
          ['AI 订阅中', d.active_subscriptions], ['AI 调用', d.ai_calls]].map(([k, v]) => (
          <div key={k} className="card text-center">
            <div className="text-3xl font-bold text-teal-700">{v}</div>
            <div className="text-sm text-gray-500 mt-1">{k}</div>
          </div>
        ))}
      </div>
      <h2 className="font-bold mt-6 mb-2">教练业绩</h2>
      <div className="card text-sm space-y-1">
        {d.coach_perf.map((c) => (
          <div key={c.coach_id} className="flex justify-between">
            <span>{c.name}</span>
            <span className="text-gray-500">客户{c.clients} · 课程{c.courses} · 签到{c.checkins}</span>
          </div>
        ))}
      </div>
    </Layout>
  );

  return (
    <Layout>
      <h1 className="text-xl font-bold mb-4">教练工作台</h1>
      <div className="grid grid-cols-2 gap-3 mb-4">
        <div className="card text-center"><div className="text-3xl font-bold text-teal-700">{d.todos.pending_diets}</div><div className="text-sm text-gray-500">待确认饮食方案</div></div>
        <div className="card text-center"><div className="text-3xl font-bold text-amber-600">{d.todos.due_reassess}</div><div className="text-sm text-gray-500">需复测客户</div></div>
      </div>
      <div className="space-y-2">
        {d.clients.map((c) => (
          <div key={c.id} className="card flex justify-between text-sm">
            <span>{LIGHT[c.status]} {c.name} <span className="text-gray-400">{c.goal}</span></span>
            <span className="text-gray-500">出勤 {Math.round((c.attendance_rate || 0) * 100)}%</span>
          </div>
        ))}
      </div>
    </Layout>
  );
}
