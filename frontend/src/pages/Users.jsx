import { useEffect, useState } from 'react';
import { api } from '../api';
import Layout from '../components/Layout';

// 账号管理（仅馆主）：教练账号 + 客户登录账号（绑定客户档案）
export default function Users() {
  const [list, setList] = useState([]);
  const [clients, setClients] = useState([]);
  const [form, setForm] = useState({ username: '', password: '', name: '', role: 'coach', client_id: '' });
  const load = () => {
    api.get('/api/auth/users').then(setList).catch(console.error);
    api.get('/api/clients').then(setClients).catch(console.error);
  };
  useEffect(load, []);
  const add = async (e) => {
    e.preventDefault();
    if (!form.username || !form.password) return alert('请填写用户名和密码');
    const payload = { username: form.username, password: form.password, name: form.name, role: form.role };
    if (form.role === 'client') {
      if (!form.client_id) return alert('客户账号需绑定客户档案');
      payload.client_id = +form.client_id;
    }
    await api.post('/api/auth/users', payload);
    setForm({ username: '', password: '', name: '', role: 'coach', client_id: '' });
    load();
  };
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  const roleName = { owner: '馆主', coach: '教练', client: '客户' };
  return (
    <Layout>
      <h1 className="text-xl font-bold mb-4">账号管理</h1>
      <form onSubmit={add} className="card mb-4 grid grid-cols-2 md:grid-cols-5 gap-2">
        <input className="input" placeholder="用户名*" value={form.username} onChange={set('username')} />
        <input className="input" placeholder="姓名" value={form.name} onChange={set('name')} />
        <input className="input" placeholder="密码*" type="password" value={form.password} onChange={set('password')} />
        <select className="input" value={form.role} onChange={set('role')}>
          <option value="coach">教练</option>
          <option value="client">客户</option>
        </select>
        {form.role === 'client' && (
          <select className="input md:col-span-5" value={form.client_id} onChange={set('client_id')}>
            <option value="">绑定客户档案…</option>
            {clients.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        )}
        <button className="btn-primary md:col-span-5">添加账号</button>
      </form>
      <div className="space-y-2">
        {list.map((u) => (
          <div key={u.id} className="card text-sm flex justify-between">
            <span className="font-medium">{u.name || u.username}</span>
            <span className="text-gray-500">{u.username} · {roleName[u.role] || u.role}</span>
          </div>
        ))}
      </div>
    </Layout>
  );
}
