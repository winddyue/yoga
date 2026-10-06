import { useEffect, useState } from 'react';
import { api } from '../api';
import Layout from '../components/Layout';

// 设置页（仅馆主）：配置第三方 API。密钥只存服务器环境变量，
// 这里只能改接口地址/模型名，密钥只显示“已配置/未配置”状态。
export default function Settings() {
  const [s, setS] = useState(null);
  const [form, setForm] = useState({ ocr_api_url: '', ai_api_url: '', ai_model: '' });
  const load = () => api.get('/api/settings').then((r) => { setS(r); setForm({ ocr_api_url: r.ocr_api_url, ai_api_url: r.ai_api_url, ai_model: r.ai_model }); }).catch(console.error);
  useEffect(load, []);
  const save = async (e) => {
    e.preventDefault();
    await api.put('/api/settings', form);
    alert('已保存');
    load();
  };
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  if (!s) return <Layout><div>加载中…</div></Layout>;
  return (
    <Layout>
      <h1 className="text-xl font-bold mb-4">第三方 API 设置</h1>
      <form onSubmit={save} className="card space-y-3 max-w-lg">
        <div><span className="label">OCR 接口地址（拍照识别体测单）</span><input className="input" value={form.ocr_api_url} onChange={set('ocr_api_url')} placeholder="https://…" /></div>
        <div className="text-sm">OCR 密钥：<span className={s.ocr_configured ? 'text-teal-600' : 'text-gray-400'}>{s.ocr_configured ? '已配置' : '未配置（请在服务器环境变量 OCR_API_KEY 中设置）'}</span></div>
        <div><span className="label">AI 接口地址</span><input className="input" value={form.ai_api_url} onChange={set('ai_api_url')} placeholder="https://…" /></div>
        <div><span className="label">AI 模型名</span><input className="input" value={form.ai_model} onChange={set('ai_model')} placeholder="如 gpt-4o-mini" /></div>
        <div className="text-sm">AI 密钥：<span className={s.ai_configured ? 'text-teal-600' : 'text-gray-400'}>{s.ai_configured ? '已配置' : '未配置（请在服务器环境变量 AI_API_KEY 中设置）'}</span></div>
        <button className="btn-primary">保存</button>
      </form>
    </Layout>
  );
}
