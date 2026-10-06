import { useEffect, useState } from 'react';
import { api } from '../api';
import Layout from '../components/Layout';

// 设置页（仅馆主）：第三方 API 配置 + AI 功能开关与定价。
// 密钥只存服务器环境变量，这里只能改接口地址/模型名/开关/定价，
// 密钥只显示"已配置/未配置"状态。
export default function Settings() {
  const [s, setS] = useState(null);
  const [form, setForm] = useState({
    ocr_api_url: '', ai_api_url: '', ai_model: '', asr_api_url: '',
    ai_enabled: false, ai_price_monthly: 0, ai_price_yearly: 0,
  });
  const load = () => api.get('/api/settings').then((r) => {
    setS(r);
    setForm({
      ocr_api_url: r.ocr_api_url || '', ai_api_url: r.ai_api_url || '',
      ai_model: r.ai_model || '', asr_api_url: r.asr_api_url || '',
      ai_enabled: !!r.ai_enabled, ai_price_monthly: r.ai_price_monthly || 0,
      ai_price_yearly: r.ai_price_yearly || 0,
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
  const [usage, setUsage] = useState([]);
  useEffect(() => { api.get('/api/subscriptions/usage').then(setUsage).catch(() => {}); }, []);
  if (!s) return <Layout><div>加载中…</div></Layout>;
  return (
    <Layout>
      <h1 className="text-xl font-bold mb-4">设置</h1>
      <form onSubmit={save} className="card space-y-3 max-w-lg">
        <h2 className="font-bold">AI 功能（高配版）</h2>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={form.ai_enabled} onChange={set('ai_enabled')} /> 启用 AI 功能
        </label>
        <div className="grid grid-cols-2 gap-2">
          <div><span className="label">包月价（元）</span><input type="number" className="input" value={form.ai_price_monthly} onChange={set('ai_price_monthly')} /></div>
          <div><span className="label">包年价（元）</span><input type="number" className="input" value={form.ai_price_yearly} onChange={set('ai_price_yearly')} /></div>
        </div>
        <div><span className="label">AI 接口地址（OpenAI 兼容，如 DeepSeek/千问）</span><input className="input" value={form.ai_api_url} onChange={set('ai_api_url')} placeholder="https://…" /></div>
        <div><span className="label">AI 模型名</span><input className="input" value={form.ai_model} onChange={set('ai_model')} placeholder="如 deepseek-chat" /></div>
        <div className="text-sm">AI 密钥：<span className={s.ai_configured ? 'text-teal-600' : 'text-gray-400'}>{s.ai_configured ? '已配置' : '未配置（请在服务器环境变量 AI_API_KEY 中设置）'}</span></div>

        <h2 className="font-bold pt-2">第三方接口</h2>
        <div><span className="label">OCR 接口地址（拍照识别体测单）</span><input className="input" value={form.ocr_api_url} onChange={set('ocr_api_url')} placeholder="https://…" /></div>
        <div className="text-sm">OCR 密钥：<span className={s.ocr_configured ? 'text-teal-600' : 'text-gray-400'}>{s.ocr_configured ? '已配置' : '未配置（环境变量 OCR_API_KEY）'}</span></div>
        <div><span className="label">语音识别接口地址</span><input className="input" value={form.asr_api_url} onChange={set('asr_api_url')} placeholder="https://…" /></div>
        <div className="text-sm">语音密钥：<span className={s.asr_configured ? 'text-teal-600' : 'text-gray-400'}>{s.asr_configured ? '已配置' : '未配置（环境变量 ASR_API_KEY）'}</span></div>
        <button className="btn-primary">保存</button>
      </form>

      <h2 className="font-bold mt-6 mb-2">AI 用量统计</h2>
      <div className="card text-sm space-y-1 max-w-lg">
        {usage.map((u, i) => <div key={i} className="flex justify-between"><span>{u.name || u.username} · {u.kind}</span><span>{u.count} 次</span></div>)}
        {usage.length === 0 && <div className="text-gray-400">暂无调用记录</div>}
      </div>
    </Layout>
  );
}
