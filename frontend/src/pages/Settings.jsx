import { useEffect, useState } from 'react';
import { api } from '../api';
import { THEMES, THEME_IDS } from '../themes';
import { useTheme } from '../theme';
import Layout from '../components/Layout';

// 设置页（仅馆主）：第三方 API 配置 + AI 功能开关 + AI 套餐管理。
// 密钥只存服务器环境变量，这里只能改接口地址/模型名/开关/套餐，
// 密钥只显示"已配置/未配置"状态。
const FEATURE_LABELS = {
  extract: '自然语言录入', ocr: 'OCR识别体测单', voice: '语音转记录',
  plan_diet: '生成训练/饮食建议', summary: '客户总结',
};

export default function Settings() {
  const { themeId, setTheme } = useTheme();
  const [s, setS] = useState(null);
  const [form, setForm] = useState({
    ocr_api_url: '', ai_api_url: '', ai_model: '', asr_api_url: '', ai_enabled: false,
  });
  const load = () => api.get('/api/settings').then((r) => {
    setS(r);
    setForm({
      ocr_api_url: r.ocr_api_url || '', ai_api_url: r.ai_api_url || '',
      ai_model: r.ai_model || '', asr_api_url: r.asr_api_url || '',
      ai_enabled: !!r.ai_enabled,
    });
  }).catch(console.error);
  useEffect(load, []);
  const save = async (e) => {
    e.preventDefault();
    await api.put('/api/settings', form);
    alert('已保存');
    load();
  };
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value });

  // AI 套餐
  const [plans, setPlans] = useState([]);
  const loadPlans = () => api.get('/api/ai/plans').then(setPlans).catch(() => {});
  useEffect(loadPlans, []);
  const [editing, setEditing] = useState(null);
  const startEdit = (p) => setEditing({
    id: p.id, name: p.name, monthly_price: p.monthly_price, yearly_price: p.yearly_price,
    ocr_per_month: p.ocr_per_month, voice_minutes_per_month: p.voice_minutes_per_month,
    llm_calls_per_month: p.llm_calls_per_month, features: { ...p.features },
  });
  const savePlan = async () => {
    await api.put(`/api/ai/plans/${editing.id}`, editing);
    setEditing(null);
    loadPlans();
  };
  const eset = (k) => (e) => setEditing({ ...editing, [k]: e.target.type === 'number' ? Number(e.target.value) : e.target.value });
  const esetFeature = (f) => (e) => setEditing({ ...editing, features: { ...editing.features, [f]: e.target.checked } });

  // 门店 AI 订阅
  const [sub, setSub] = useState(null);
  const loadSub = () => api.get('/api/ai/subscription').then(setSub).catch(() => {});
  useEffect(loadSub, []);
  const [newSub, setNewSub] = useState({ plan_id: '', days: 30, status: 'active', note: '' });
  const activate = async (e) => {
    e.preventDefault();
    if (!newSub.plan_id) return alert('请选择套餐');
    await api.post('/api/ai/subscriptions', { ...newSub, plan_id: Number(newSub.plan_id), days: Number(newSub.days) });
    setNewSub({ plan_id: '', days: 30, status: 'active', note: '' });
    loadSub();
  };

  const [usage, setUsage] = useState([]);
  useEffect(() => { api.get('/api/ai/usage').then(setUsage).catch(() => {}); }, []);

  if (!s) return <Layout><div>加载中…</div></Layout>;
  return (
    <Layout>
      <h1 className="text-xl font-bold mb-4">设置</h1>

      <div className="card max-w-lg mb-4">
        <h2 className="font-bold mb-1">界面风格</h2>
        <p className="text-sm text-muted mb-3">选择喜欢的配色，立即生效（仅保存在本浏览器）</p>
        <div className="grid grid-cols-4 md:grid-cols-6 gap-2.5">
          {THEME_IDS.map((id) => {
            const t = THEMES[id];
            const active = id === themeId;
            return (
              <button key={id} type="button" onClick={() => setTheme(id)}
                className={`rounded-2xl p-2.5 text-center border-2 transition ${active ? 'border-brand-500 shadow-soft' : 'border-transparent hover:border-sand'}`}
                style={{ background: t.bg }} title={t.name}>
                <span className="block w-8 h-8 rounded-full mx-auto mb-1.5 border border-black/5" style={{ background: t.pri }} />
                <span className="block text-xs leading-tight" style={{ color: t.txt }}>{t.name}</span>
                {active && <span className="block text-xs mt-0.5" style={{ color: t.prid }}>✓ 使用中</span>}
              </button>
            );
          })}
        </div>
      </div>

      <form onSubmit={save} className="card space-y-3 max-w-lg">
        <h2 className="font-bold">AI 功能（高配版）</h2>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={form.ai_enabled} onChange={set('ai_enabled')} /> 启用 AI 功能
        </label>
        <div><span className="label">AI 接口地址（OpenAI 兼容，如 DeepSeek/千问）</span><input className="input" value={form.ai_api_url} onChange={set('ai_api_url')} placeholder="https://…" /></div>
        <div><span className="label">AI 模型名</span><input className="input" value={form.ai_model} onChange={set('ai_model')} placeholder="如 deepseek-chat" /></div>
        <div className="text-sm">AI 密钥：<span className={s.ai_configured ? 'text-brand-600' : 'text-clay'}>{s.ai_configured ? '已配置' : '未配置（请在服务器环境变量 AI_API_KEY 中设置）'}</span></div>

        <h2 className="font-bold pt-2">第三方接口</h2>
        <div><span className="label">OCR 接口地址（拍照识别体测单）</span><input className="input" value={form.ocr_api_url} onChange={set('ocr_api_url')} placeholder="https://…" /></div>
        <div className="text-sm">OCR 密钥：<span className={s.ocr_configured ? 'text-brand-600' : 'text-clay'}>{s.ocr_configured ? '已配置' : '未配置（环境变量 OCR_API_KEY）'}</span></div>
        <div><span className="label">语音识别接口地址</span><input className="input" value={form.asr_api_url} onChange={set('asr_api_url')} placeholder="https://…" /></div>
        <div className="text-sm">语音密钥：<span className={s.asr_configured ? 'text-brand-600' : 'text-clay'}>{s.asr_configured ? '已配置' : '未配置（环境变量 ASR_API_KEY）'}</span></div>
        <button className="btn-primary">保存</button>
      </form>

      <h2 className="font-bold mt-6 mb-2">AI 套餐（门店订阅）</h2>
      <div className="card text-sm space-y-3 max-w-2xl">
        {sub?.subscription
          ? <div>当前订阅：<b>{sub.subscription.plan_name}</b>（{sub.subscription.status}，到期 {sub.subscription.expires_at?.slice(0, 10)}）</div>
          : <div className="text-clay">门店暂无有效 AI 订阅</div>}
        {sub?.quotas && (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
            {Object.entries(sub.quotas).map(([k, q]) => (
              <div key={k} className="border rounded p-2 text-center">
                <div className="font-medium">{q.label}</div>
                <div className="text-xs text-muted">{q.enabled ? `剩 ${q.remaining}/${q.limit}` : '未开通'}</div>
              </div>
            ))}
          </div>
        )}
        <form onSubmit={activate} className="flex flex-wrap gap-2 items-end pt-2 border-t">
          <div><span className="label">套餐</span>
            <select className="input" value={newSub.plan_id} onChange={(e) => setNewSub({ ...newSub, plan_id: e.target.value })}>
              <option value="">选择套餐</option>
              {plans.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </div>
          <div><span className="label">天数</span><input type="number" className="input w-24" value={newSub.days} onChange={(e) => setNewSub({ ...newSub, days: e.target.value })} /></div>
          <div><span className="label">状态</span>
            <select className="input" value={newSub.status} onChange={(e) => setNewSub({ ...newSub, status: e.target.value })}>
              <option value="active">有效</option>
              <option value="trialing">试用中</option>
              <option value="paused">暂停</option>
            </select>
          </div>
          <button className="btn-primary">手动开通</button>
        </form>
        <div className="text-xs text-clay">手动开通为原型流程；未来在线收款后改为支付回调自动激活。</div>
      </div>

      <h2 className="font-bold mt-6 mb-2">套餐配置</h2>
      <div className="space-y-2 max-w-2xl">
        {plans.map((p) => (
          <div key={p.id} className="card text-sm">
            {editing?.id === p.id ? (
              <div className="space-y-2">
                <div className="font-bold">{editing.name}</div>
                <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
                  <div><span className="label">月价</span><input type="number" className="input" value={editing.monthly_price} onChange={eset('monthly_price')} /></div>
                  <div><span className="label">年价</span><input type="number" className="input" value={editing.yearly_price} onChange={eset('yearly_price')} /></div>
                  <div><span className="label">OCR/月</span><input type="number" className="input" value={editing.ocr_per_month} onChange={eset('ocr_per_month')} /></div>
                  <div><span className="label">语音分钟/月</span><input type="number" className="input" value={editing.voice_minutes_per_month} onChange={eset('voice_minutes_per_month')} /></div>
                  <div><span className="label">模型调用/月</span><input type="number" className="input" value={editing.llm_calls_per_month} onChange={eset('llm_calls_per_month')} /></div>
                </div>
                <div className="flex flex-wrap gap-3">
                  {Object.entries(FEATURE_LABELS).map(([f, label]) => (
                    <label key={f} className="flex items-center gap-1">
                      <input type="checkbox" checked={!!editing.features[f]} onChange={esetFeature(f)} /> {label}
                    </label>
                  ))}
                </div>
                <div className="space-x-2">
                  <button type="button" className="btn-primary" onClick={savePlan}>保存</button>
                  <button type="button" className="btn-ghost" onClick={() => setEditing(null)}>取消</button>
                </div>
              </div>
            ) : (
              <div className="flex justify-between items-center">
                <div>
                  <span className="font-bold">{p.name}</span>
                  <span className="text-muted ml-2">¥{p.monthly_price}/月 · ¥{p.yearly_price}/年</span>
                  <div className="text-xs text-muted mt-1">
                    OCR {p.ocr_per_month}/月 · 语音 {p.voice_minutes_per_month}分钟/月 · 模型 {p.llm_calls_per_month}/月 ·
                    功能：{Object.entries(p.features || {}).filter(([, v]) => v).map(([f]) => FEATURE_LABELS[f]).join('、') || '无'}
                  </div>
                </div>
                <button className="btn-ghost" onClick={() => startEdit(p)}>编辑</button>
              </div>
            )}
          </div>
        ))}
      </div>

      <h2 className="font-bold mt-6 mb-2">AI 用量统计</h2>
      <div className="card text-sm space-y-1 max-w-lg">
        {usage.map((u, i) => <div key={i} className="flex justify-between"><span>{u.name || u.username} · {u.kind}</span><span>{u.kind === 'voice' ? `${u.amount} 分钟` : `${u.count} 次`}</span></div>)}
        {usage.length === 0 && <div className="text-clay">暂无调用记录</div>}
      </div>
    </Layout>
  );
}
