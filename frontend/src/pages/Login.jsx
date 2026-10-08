import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../auth';

// 登录页
export default function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [err, setErr] = useState('');
  const { login } = useAuth();
  const nav = useNavigate();
  const submit = async (e) => {
    e.preventDefault();
    try { await login(username, password); nav('/'); }
    catch (e2) { setErr(e2.message); }
  };
  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <form onSubmit={submit} className="card w-full max-w-xs space-y-3">
        <div className="w-11 h-11 rounded-full bg-brand-100 text-brand-600 flex items-center justify-center text-xl font-bold">瑜</div>
        <h1 className="font-bold text-lg text-brand-700 tracking-widest">客户管理登录</h1>
        <div><span className="label">用户名</span><input className="input" value={username} onChange={(e) => setUsername(e.target.value)} /></div>
        <div><span className="label">密码</span><input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} /></div>
        {err && <div className="text-[#C07878] text-sm">{err}</div>}
        <button className="btn-primary w-full">登录</button>
        <div className="text-xs text-clay">首次使用：用 admin / admin123 登录（请尽快修改）</div>
      </form>
    </div>
  );
}
