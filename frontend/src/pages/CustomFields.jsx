import { useEffect, useState } from 'react';
import { api } from '../api';
import Layout from '../components/Layout';

// 自定义字段管理（仅馆主）：增减客户/评估的自定义字段
export default function CustomFields() {
  const [list, setList] = useState([]);
  const [form, setForm] = useState({ name: '', field_type: 'text', target: 'assessment' });
  const load = () => api.get('/api/custom-fields').then(setList).catch(console.error);
  useEffect(load, []);
  const add = async (e) => {
    e.preventDefault();
    if (!form.name) return alert('请填写字段名');
    await api.post('/api/custom-fields', form);
    setForm({ name: '', field_type: 'text', target: 'assessment' });
    load();
  };
  const del = async (id) => {
    if (!window.confirm('删除该自定义字段？')) return;
    await api.del(`/api/custom-fields/${id}`);
    load();
  };
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  return (
    <Layout>
      <h1 className="text-xl font-bold mb-4">自定义字段</h1>
      <form onSubmit={add} className="card mb-4 grid grid-cols-2 md:grid-cols-4 gap-2">
        <input className="input" placeholder="字段名*（如：腰臀比）" value={form.name} onChange={set('name')} />
        <select className="input" value={form.field_type} onChange={set('field_type')}>
          <option value="text">文本</option><option value="number">数字</option>
        </select>
        <select className="input" value={form.target} onChange={set('target')}>
          <option value="assessment">评估记录</option><option value="client">客户档案</option>
        </select>
        <button className="btn-primary">添加字段</button>
      </form>
      <div className="space-y-2">
        {list.map((f) => (
          <div key={f.id} className="card text-sm flex justify-between">
            <span>{f.name}（{f.field_type === 'number' ? '数字' : '文本'} · {f.target === 'client' ? '客户档案' : '评估记录'}）</span>
            <button className="text-[#C07878]" onClick={() => del(f.id)}>删除</button>
          </div>
        ))}
        {!list.length && <div className="text-clay text-sm">暂无自定义字段</div>}
      </div>
    </Layout>
  );
}
