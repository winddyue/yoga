// API 封装：统一处理 token 与错误
const BASE = import.meta.env.VITE_API_URL || '';

function headers(json = true) {
  const h = {};
  if (json) h['Content-Type'] = 'application/json';
  const t = localStorage.getItem('token');
  if (t) h['Authorization'] = `Bearer ${t}`;
  return h;
}

async function req(path, opts = {}) {
  const res = await fetch(BASE + path, {
    ...opts,
    headers: { ...headers(opts.body instanceof FormData ? false : true), ...(opts.headers || {}) },
  });
  if (res.status === 401) {
    localStorage.removeItem('token');
    window.location.href = '/login';
    throw new Error('登录已过期');
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `请求失败(${res.status})`);
  }
  return res.json();
}

export const api = {
  get: (p) => req(p),
  post: (p, data) => req(p, { method: 'POST', body: JSON.stringify(data) }),
  put: (p, data) => req(p, { method: 'PUT', body: JSON.stringify(data) }),
  del: (p) => req(p, { method: 'DELETE' }),
  // 登录用表单格式
  login: async (username, password) => {
    const body = new URLSearchParams({ username, password });
    const res = await fetch(BASE + '/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body,
    });
    if (!res.ok) throw new Error('用户名或密码错误');
    return res.json();
  },
  upload: async (path, file) => {
    const fd = new FormData();
    fd.append('file', file);
    const res = await fetch(BASE + path, { method: 'POST', headers: headers(false), body: fd });
    if (!res.ok) throw new Error('上传失败');
    return res.json();
  },
};
