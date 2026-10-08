import { useEffect, useState } from 'react';
import { api } from '../api';
import { useAuth } from '../auth';
import Layout from '../components/Layout';
import TrendChart from '../components/TrendChart';
import BarChart from '../components/BarChart';

const LIGHT = { red: '🔴', yellow: '🟡', green: '🟢' };
const STATUS_ORDER = { red: 0, yellow: 1, green: 2 };
const STATUS_NAME = { red: '需关注', yellow: '待跟进', green: '正常' };

// 趋势指标配置：减脂场景下，体重/体脂/腰围下降是好事（sage 绿），上升是坏事（柔红）
const METRICS = {
  weight: { label: '体重', unit: 'kg', color: '#B76E79' },
  body_fat: { label: '体脂率', unit: '%', color: '#D9A85F' },
  waist: { label: '腰围', unit: 'cm', color: '#9CAF88' },
  hip: { label: '臀围', unit: 'cm', color: '#B89B7E' },
};
const changeCls = (v) => (v < 0 ? 'text-sage-700' : v > 0 ? 'text-[#C07878]' : 'text-clay');

// 出勤目标差距圆环：当前出勤率 vs 100% 目标（行业共识做法，一眼看到差距）
function GoalRing({ rate }) {
  const R = 34, C = 2 * Math.PI * R;
  const pct = Math.round((rate || 0) * 100);
  return (
    <svg width="96" height="96" viewBox="0 0 96 96">
      <circle cx="48" cy="48" r={R} fill="none" stroke="#F1E9DE" strokeWidth="10" />
      <circle cx="48" cy="48" r={R} fill="none" stroke="#B76E79" strokeWidth="10"
        strokeLinecap="round" strokeDasharray={C} strokeDashoffset={C * (1 - (rate || 0))}
        transform="rotate(-90 48 48)" />
      <text x="48" y="48" textAnchor="middle" dominantBaseline="central"
        fontSize="18" fontWeight="bold" fill="#854750">{pct}%</text>
    </svg>
  );
}

// 总览页：按角色展示不同汇总
export default function Dashboard() {
  const { user } = useAuth();
  const [d, setD] = useState(null);
  const [charts, setCharts] = useState(null);
  const [staffClients, setStaffClients] = useState(null);
  const [metric, setMetric] = useState('weight');

  useEffect(() => {
    const url = user.role === 'client' ? '/api/dashboard/me/summary'
      : user.role === 'owner' ? '/api/dashboard/owner/overview'
      : '/api/dashboard/coach/overview';
    api.get(url).then(setD).catch(console.error);
    // 客户：图表数据包；馆主：全馆客户状态（阶段分布/管理表）
    if (user.role === 'client') api.get('/api/dashboard/me/charts').then(setCharts).catch(console.error);
    if (user.role === 'owner') api.get('/api/dashboard/coach/overview').then(setStaffClients).catch(console.error);
  }, [user.role]);
  if (!d) return <Layout><div>加载中…</div></Layout>;

  // ---------------- 客户：我的进展 ----------------
  if (user.role === 'client') {
    const m = METRICS[metric];
    const t = charts?.trends;
    return (
      <Layout>
        <h1 className="text-xl font-bold mb-4">我的进展</h1>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[['目标', d.goal], ['出勤率', `${Math.round((d.attendance_rate || 0) * 100)}%`],
            ['体重变化', `${d.weight_change > 0 ? '+' : ''}${d.weight_change}kg`],
            ['饮食方案已确认', d.diet_confirmed]].map(([k, v]) => (
            <div key={k} className="card text-center">
              <div className="text-2xl font-bold text-brand-700">{v}</div>
              <div className="text-sm text-muted mt-1">{k}</div>
            </div>
          ))}
        </div>

        <div className="card mt-4 flex items-center gap-4">
          <GoalRing rate={d.attendance_rate} />
          <div>
            <div className="font-medium">出勤目标差距</div>
            <div className="text-sm text-muted mt-1">
              当前出勤率 {Math.round((d.attendance_rate || 0) * 100)}%，目标 100%
            </div>
            <div className="text-sm text-muted">
              还差 {100 - Math.round((d.attendance_rate || 0) * 100)} 个百分点
            </div>
          </div>
        </div>

        {charts && t?.dates?.length > 0 && (
          <>
            <div className="card mt-4">
              <div className="flex items-center justify-between mb-2">
                <h2 className="font-medium">身体趋势</h2>
                <div className="flex gap-1">
                  {Object.entries(METRICS).map(([k, cfg]) => (
                    <button key={k} onClick={() => setMetric(k)}
                      className={`text-xs px-2 py-1 rounded ${metric === k ? 'bg-brand-600 text-white' : 'bg-cream text-muted'}`}>
                      {cfg.label}
                    </button>
                  ))}
                </div>
              </div>
              <TrendChart dates={t.dates} series={t[metric]} unit={m.unit} color={m.color} />
              <div className="flex flex-wrap gap-4 mt-2 text-sm">
                {Object.entries(METRICS).map(([k, cfg]) => {
                  if (k === 'hip') return null;
                  const v = charts.changes?.[k] ?? 0;
                  return (
                    <span key={k} className="text-muted">{cfg.label}
                      <b className={`ml-1 ${changeCls(v)}`}>{v > 0 ? '+' : ''}{v}{cfg.unit}</b>
                    </span>
                  );
                })}
                <span className="text-clay text-xs self-center">相对首次评估</span>
              </div>
            </div>
            <div className="card mt-4">
              <h2 className="font-medium mb-2">月度出勤率（近 6 个月）</h2>
              <BarChart
                labels={charts.monthly_attendance.map((x) => x.month.slice(5) + '月')}
                values={charts.monthly_attendance.map((x) => Math.round(x.rate * 100))}
                unit="%" />
            </div>
          </>
        )}
        <div className="card mt-4 text-sm">当前状态 {LIGHT[d.status] || ''} · 待上课程 {d.upcoming_bookings} 节</div>
      </Layout>
    );
  }

  // ---------------- 馆主：经营概况 ----------------
  if (user.role === 'owner') {
    const clients = (staffClients?.clients || []).slice()
      .sort((a, b) => (STATUS_ORDER[a.status] ?? 9) - (STATUS_ORDER[b.status] ?? 9));
    const cnt = { red: 0, yellow: 0, green: 0 };
    clients.forEach((c) => { if (cnt[c.status] !== undefined) cnt[c.status] += 1; });
    const total = clients.length || 1;
    return (
      <Layout>
        <h1 className="text-xl font-bold mb-4">经营概况</h1>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[['总客户', d.total_clients], ['近30天新增', d.new_clients_30d],
            ['近30天活跃', d.active_clients_30d], ['课程数', d.course_count],
            ['近30天预约', d.bookings_30d], ['累计签到', d.total_checkins],
            ['AI 订阅中', d.active_subscriptions], ['AI 调用', d.ai_calls]].map(([k, v]) => (
            <div key={k} className="card text-center">
              <div className="text-3xl font-bold text-brand-700">{v}</div>
              <div className="text-sm text-muted mt-1">{k}</div>
            </div>
          ))}
        </div>

        <h2 className="font-bold mt-6 mb-2">会员分层</h2>
        <div className="grid grid-cols-4 gap-3">
          {[['新客', d.new_clients_30d, '近30天新增', 'bg-sage-100 text-sage-700'],
            ['活跃', cnt.green, '绿灯客户', 'bg-brand-100 text-brand-700'],
            ['沉默', cnt.yellow, '黄灯客户', 'bg-[#FDF6E8] text-[#96690F]'],
            ['流失风险', cnt.red, '红灯客户', 'bg-[#FBF0EE] text-[#A85D5D]']].map(([k, v, sub, cls]) => (
            <div key={k} className={`card text-center ${cls}`}>
              <div className="text-3xl font-bold">{v}</div>
              <div className="text-sm font-medium mt-1">{k}</div>
              <div className="text-xs opacity-70">{sub}</div>
            </div>
          ))}
        </div>

        <h2 className="font-bold mt-6 mb-2">客户阶段分布</h2>
        <div className="card">
          <div className="flex h-5 rounded overflow-hidden mb-2">
            {[['red', '#D98880'], ['yellow', '#D9A85F'], ['green', '#9CAF88']].map(([k, color]) => (
              <div key={k} style={{ width: `${(cnt[k] / total) * 100}%`, background: color }}
                title={`${STATUS_NAME[k]} ${cnt[k]}人`} />
            ))}
          </div>
          <div className="flex gap-4 text-sm text-muted">
            <span>🔴 需关注 <b>{cnt.red}</b></span>
            <span>🟡 待跟进 <b>{cnt.yellow}</b></span>
            <span>🟢 正常 <b>{cnt.green}</b></span>
          </div>
        </div>

        <h2 className="font-bold mt-6 mb-2">客户管理</h2>
        <div className="card overflow-x-auto">
          <table className="w-full text-sm whitespace-nowrap">
            <thead><tr className="text-clay text-left">
              <th className="py-1 pr-3">状态</th><th className="py-1 pr-3">姓名</th>
              <th className="py-1 pr-3">目标</th><th className="py-1 pr-3">出勤率</th>
              <th className="py-1 pr-3">上次评估</th><th className="py-1">建议动作</th>
            </tr></thead>
            <tbody>
              {clients.map((c) => (
                <tr key={c.id} className="border-t border-sand">
                  <td className="py-2 pr-3">{LIGHT[c.status]}</td>
                  <td className="py-2 pr-3 font-medium">{c.name}</td>
                  <td className="py-2 pr-3 text-muted">{c.goal || '-'}</td>
                  <td className="py-2 pr-3">{Math.round((c.attendance_rate || 0) * 100)}%</td>
                  <td className="py-2 pr-3 text-muted">
                    {c.days_since_assessment == null ? '尚未评估' : `${c.days_since_assessment}天前`}
                  </td>
                  <td className="py-2 text-[#96690F]">{c.action || '-'}</td>
                </tr>
              ))}
              {!clients.length && <tr><td colSpan="6" className="py-3 text-clay">暂无客户</td></tr>}
            </tbody>
          </table>
        </div>

        <h2 className="font-bold mt-6 mb-2">教练业绩</h2>
        <div className="card text-sm space-y-1">
          {d.coach_perf.map((c) => (
            <div key={c.coach_id} className="flex justify-between">
              <span>{c.name}</span>
              <span className="text-muted">客户{c.clients} · 课程{c.courses} · 签到{c.checkins}</span>
            </div>
          ))}
        </div>
      </Layout>
    );
  }

  // ---------------- 教练：工作台（红灯优先，其次黄灯） ----------------
  const coachClients = (d.clients || []).slice()
    .sort((a, b) => (STATUS_ORDER[a.status] ?? 9) - (STATUS_ORDER[b.status] ?? 9));
  return (
    <Layout>
      <h1 className="text-xl font-bold mb-4">教练工作台</h1>
      <div className="grid grid-cols-2 gap-3 mb-4">
        <div className="card text-center"><div className="text-3xl font-bold text-brand-700">{d.todos.pending_diets}</div><div className="text-sm text-muted">待确认饮食方案</div></div>
        <div className="card text-center"><div className="text-3xl font-bold text-[#B57E35]">{d.todos.due_reassess}</div><div className="text-sm text-muted">需复测客户</div></div>
      </div>
      <div className="space-y-2">
        {coachClients.map((c) => (
          <div key={c.id} className="card flex justify-between text-sm">
            <span>{LIGHT[c.status]} {c.name} <span className="text-clay">{c.goal}</span></span>
            <span className="text-muted">
              出勤 {Math.round((c.attendance_rate || 0) * 100)}%
              {c.days_since_assessment == null ? ' · 尚未评估' : ` · 距上次评估${c.days_since_assessment}天`}
            </span>
          </div>
        ))}
      </div>
    </Layout>
  );
}
