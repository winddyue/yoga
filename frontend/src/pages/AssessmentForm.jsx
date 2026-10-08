import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { api } from '../api';
import Layout from '../components/Layout';
import QrScanner from '../components/QrScanner';

// 新增评估：手填 + 拍照上传 + 扫码自动填
const FIELDS = [
  ['date', '评估日期', 'date'], ['weight_kg', '体重(kg)', 'number'], ['body_fat_pct', '体脂率(%)', 'number'],
  ['muscle_kg', '肌肉量(kg)', 'number'], ['bmi', 'BMI', 'number'], ['visceral_fat', '内脏脂肪', 'number'],
  ['chest_cm', '胸围(cm)', 'number'], ['waist_cm', '腰围(cm)', 'number'], ['hip_cm', '臀围(cm)', 'number'],
  ['arm_cm', '上臂围(cm)', 'number'], ['thigh_cm', '大腿围(cm)', 'number'],
  ['resting_hr', '静息心率', 'number'], ['blood_pressure', '血压(如120/80)', 'text'],
];
const EMPTY = Object.fromEntries(FIELDS.map(([k]) => [k, '']));

export default function AssessmentForm() {
  const { id } = useParams();
  const nav = useNavigate();
  const [form, setForm] = useState({ ...EMPTY, injuries: '' });
  const [scan, setScan] = useState(false);
  const [msg, setMsg] = useState('');
  // 自定义字段（target=assessment，由馆主在"自定义字段"页维护）
  const [cfFields, setCfFields] = useState([]);
  const [cfVals, setCfVals] = useState({});
  useEffect(() => {
    api.get('/api/custom-fields')
      .then((r) => setCfFields((r || []).filter((f) => f.target === 'assessment')))
      .catch(() => {});
  }, []);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  const setCf = (id) => (e) => setCfVals({ ...cfVals, [id]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    const num = (v) => (v === '' ? 0 : +v);
    const payload = { ...form };
    FIELDS.forEach(([k, , t]) => { if (t === 'number') payload[k] = num(form[k]); });
    // 自定义字段并入 custom_values（key 为字段 id 字符串；空值不保存）
    const cv = {};
    cfFields.forEach((f) => {
      const v = cfVals[f.id];
      if (v === '' || v === undefined || v === null) return;
      cv[String(f.id)] = f.field_type === 'number' ? num(v) : v;
    });
    if (Object.keys(cv).length) payload.custom_values = cv;
    await api.post(`/api/clients/${id}/assessments`, payload);
    nav(`/clients/${id}`);
  };

  // 拍照上传体测单（后端预留 OCR 接口，当前仅保存照片）
  const onPhoto = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setMsg('上传中…');
    try {
      const r = await api.upload(`/api/clients/${id}/photo`, file);
      setForm({ ...form, photo_path: r.photo_path });
      // 尝试 OCR 识别（未配置会返回明确提示）
      try {
        const fd = new FormData(); fd.append('file', file);
        const res = await fetch('/api/ocr-extract', {
          method: 'POST',
          headers: { Authorization: `Bearer ${localStorage.getItem('token')}` },
          body: fd,
        });
        const data = await res.json();
        if (res.ok && data.data) { setForm({ ...form, ...data.data }); setMsg('已识别并填入'); }
        else setMsg(data.detail || '照片已保存');
      } catch { setMsg('照片已保存'); }
    } catch { setMsg('上传失败'); }
  };

  return (
    <Layout>
      <h1 className="text-xl font-bold mb-4">新增评估</h1>
      <div className="flex gap-2 mb-4">
        <label className="btn-ghost cursor-pointer">拍照/上传体测单<input type="file" accept="image/*" className="hidden" onChange={onPhoto} /></label>
        <button type="button" className="btn-ghost" onClick={() => setScan(true)}>扫码录入</button>
        {msg && <span className="text-sm text-muted self-center">{msg}</span>}
      </div>
      {scan && <QrScanner onClose={() => setScan(false)} onScan={(d) => { setForm({ ...EMPTY, injuries: '', ...d }); setScan(false); }} />}
      <form onSubmit={submit} className="card grid grid-cols-2 md:grid-cols-3 gap-3">
        {FIELDS.map(([k, label, t]) => (
          <div key={k}><span className="label">{label}</span><input className="input" type={t} value={form[k]} onChange={set(k)} /></div>
        ))}
        <div className="col-span-2 md:col-span-3">
          <span className="label">伤病史/注意事项</span>
          <textarea className="input" rows="2" value={form.injuries} onChange={set('injuries')} />
        </div>
        {cfFields.length > 0 && (
          <>
            <div className="col-span-2 md:col-span-3"><span className="label font-bold">自定义字段</span></div>
            {cfFields.map((f) => (
              <div key={f.id}>
                <span className="label">{f.name}</span>
                <input className="input" type={f.field_type === 'number' ? 'number' : 'text'}
                  value={cfVals[f.id] ?? ''} onChange={setCf(f.id)} />
              </div>
            ))}
          </>
        )}
        <button className="btn-primary col-span-2 md:col-span-3">保存评估</button>
      </form>
    </Layout>
  );
}
