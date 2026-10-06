import { useEffect, useState } from 'react';
import { api } from '../api';
import Layout from '../components/Layout';

// 教练账号管理（仅馆主）
export default function Users() {
  const [list, setList] = useState([]);
  const [form, setForm] = useState({ username: '', password: '', name: '' });
  const load = () => api.get('/api/auth/users').then(setList).catch(console.error);
  useEffect(load, []);
  const add = async (e) => {
    e.preventDefault();
    if (!form.username || !form.password) return alert('请填写用户名和密码');
    await api.post('/api/auth/users', { ...form, role: 'coach' });
    setForm({ username: '', password: '', name: '' });
    load();
  };
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  return (
    <Layout>
      <h1 className="text-xl font-bold mb-4">教练账号</h1>
      <form onSubmit={add} className="card mb-4 grid grid-cols-2 md:grid-cols-4 gap-2">
        <input className="input" placeholder="用户名*" value={form.username} onChange={set('username')} />
        <input className="input" placeholder="姓名" value={form.name} onChange={set('name')} />
        <input className="input" placeholder="密码*" type="password" value={form.password} onChange={set('password')} />
        <button className="btn-primary">添加教练</button>
      </form>
      <div className="space-y-2">
        {list.map((u) => (
          <div key={u.id} className="card text-sm flex justify-between">
            <span className="font-medium">{u.name || u.username}</span>
            <span className="text-gray-500">{u.username} · {u.role === 'owner' ? '馆主' : '教练'}</span>
          </div>
        ))}
      </div>
    </Layout>
  );
}
