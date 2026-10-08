import { useEffect, useState } from 'react';
import { api } from '../api';
import Layout from '../components/Layout';

// 智能录入：聊天框自由文本 / 语音上传 -> 大模型抽字段 -> 人工确认 -> 入库
const FIELD_LABELS = {
  weight_kg: '体重(kg)', body_fat_pct: '体脂率(%)', muscle_kg: '肌肉量(kg)',
  bmi: 'BMI', visceral_fat: '内脏脂肪', chest_cm: '胸围(cm)', waist_cm: '腰围(cm)',
  hip_cm: '臀围(cm)', arm_cm: '上臂围(cm)', thigh_cm: '大腿围(cm)',
  resting_hr: '静息心率', blood_pressure: '血压', injuries: '伤病史',
  height_cm: '身高(cm)', age: '年龄',
};

export default function Intake() {
  const [clients, setClients] = useState([]);
  const [clientId, setClientId] = useState('');
  const [text, setText] = useState('');
  const [fields, setFields] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => { api.get('/api/clients').then(setClients).catch(console.error); }, []);

  const doExtract = async (inputText) => {
    setBusy(true);
    try {
      const r = await api.post('/api/intake/extract', { text: inputText });
      setFields(r.fields);
    } catch (e) { alert(e.message); } finally { setBusy(false); }
  };

  const doVoice = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setBusy(true);
    try {
      const r = await api.upload('/api/intake/voice', file);
      setText(r.text);
      await doExtract(r.text);
    } catch (err) { alert(err.message); } finally { setBusy(false); }
  };

  const confirm = async () => {
    if (!clientId) return alert('请先选择客户');
    try {
      await api.post('/api/intake/confirm', { client_id: +clientId, fields });
      alert('已入库');
      setFields(null); setText('');
    } catch (e) { alert(e.message); }
  };

  return (
    <Layout>
      <h1 className="text-xl font-bold mb-4">智能录入</h1>
      <div className="card space-y-3 max-w-2xl">
        <div>
          <span className="label">选择客户</span>
          <select className="input" value={clientId} onChange={(e) => setClientId(e.target.value)}>
            <option value="">请选择…</option>
            {clients.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </div>
        <div>
          <span className="label">聊天框输入（自由文本，如"身高175体重80体脂25腰围82"）</span>
          <textarea className="input" rows={3} value={text} onChange={(e) => setText(e.target.value)} />
        </div>
        <div className="flex gap-2">
          <button className="btn-primary" disabled={busy || !text} onClick={() => doExtract(text)}>
            {busy ? '识别中…' : '提取字段'}
          </button>
          <label className="btn cursor-pointer">
            语音上传
            <input type="file" accept="audio/*" className="hidden" onChange={doVoice} />
          </label>
        </div>
        <p className="text-xs text-clay">拍照识别请在评估页上传体测单照片（需配置 OCR）。三路录入统一经人工确认后入库。</p>
      </div>

      {fields && (
        <div className="card mt-4 max-w-2xl">
          <h2 className="font-bold mb-2">待确认字段（可修改）</h2>
          <div className="grid grid-cols-2 gap-2">
            {Object.entries(fields).map(([k, v]) => (
              <div key={k} className="flex items-center gap-2">
                <span className="text-sm text-muted w-24 shrink-0">{FIELD_LABELS[k] || k}</span>
                <input className="input" value={v} onChange={(e) => setFields({ ...fields, [k]: e.target.value })} />
              </div>
            ))}
          </div>
          <button className="btn-primary mt-3" onClick={confirm}>确认入库</button>
        </div>
      )}
    </Layout>
  );
}
