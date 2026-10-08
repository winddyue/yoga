import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';
import Layout from '../components/Layout';

const GOALS = ['减脂', '增肌', '塑形', '体态改善'];

// 客户列表 + 新增客户
export default function Clients() {
  const [list, setList] = useState([]);
  const [form, setForm] = useState({ name: '', gender: '女', age: '', height_cm: '', phone: '', goal: '减脂' });
  const load = () => api.get('/api/clients').then(setList).catch(console.error);
  useEffect(load, []);
  const add = async (e) => {
    e.preventDefault();
    if (!form.name) return alert('请填写姓名');
    await api.post('/api/clients', { ...form, age: +form.age || 0, height_cm: +form.height_cm || 0 });
    setForm({ name: '', gender: '女', age: '', height_cm: '', phone: '', goal: '减脂' });
    load();
  };
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  return (
    <Layout>
      <h1 className="text-xl font-bold mb-4">客户</h1>
      <form onSubmit={add} className="card mb-4 grid grid-cols-2 md:grid-cols-4 gap-2">
        <input className="input" placeholder="姓名*" value={form.name} onChange={set('name')} />
        <select className="input" value={form.gender} onChange={set('gender')}><option>女</option><option>男</option></select>
        <input className="input" placeholder="年龄" value={form.age} onChange={set('age')} />
        <input className="input" placeholder="身高(cm)" value={form.height_cm} onChange={set('height_cm')} />
        <input className="input" placeholder="电话" value={form.phone} onChange={set('phone')} />
        <select className="input" value={form.goal} onChange={set('goal')}>{GOALS.map((g) => <option key={g}>{g}</option>)}</select>
        <button className="btn-primary col-span-2 md:col-span-2">新增客户</button>
      </form>
      <div className="grid gap-2">
        {list.map((c) => (
          <Link key={c.id} to={`/clients/${c.id}`} className="card hover:border-brand-300 flex justify-between">
            <span className="font-medium">{c.name}</span>
            <span className="text-sm text-muted">{c.goal} · {c.phone}</span>
          </Link>
        ))}
        {!list.length && <div className="text-clay text-sm">暂无客户</div>}
      </div>
    </Layout>
  );
}
