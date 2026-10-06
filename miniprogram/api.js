// API 客户端：指向 FastAPI 后端，JWT 登录态复用（与 Web 版同一套接口）
// 使用前在下方修改 BASE 为后端地址；生产环境必须用 HTTPS 域名并完成 ICP 备案
const BASE = 'http://127.0.0.1:8000';

function headers(json = true) {
  const h = {};
  if (json) h['content-type'] = 'application/json';
  const t = wx.getStorageSync('token');
  if (t) h['Authorization'] = `Bearer ${t}`;
  return h;
}

function req(path, { method = 'GET', data = null } = {}) {
  return new Promise((resolve, reject) => {
    wx.request({
      url: BASE + path,
      method,
      data,
      header: headers(!(data instanceof FormData)),
      success(res) {
        if (res.statusCode === 401) {
          wx.removeStorageSync('token');
          wx.redirectTo({ url: '/pages/login/login' });
          return reject(new Error('登录已过期'));
        }
        if (res.statusCode >= 400) {
          return reject(new Error((res.data && res.data.detail) || `请求失败(${res.statusCode})`));
        }
        resolve(res.data);
      },
      fail: reject,
    });
  });
}

module.exports = {
  BASE,
  get: (p) => req(p),
  post: (p, data) => req(p, { method: 'POST', data }),
  put: (p, data) => req(p, { method: 'PUT', data }),
  del: (p) => req(p, { method: 'DELETE' }),
  // 登录：用户名 + 密码，token 存本地
  login(username, password) {
    return new Promise((resolve, reject) => {
      wx.request({
        url: `${BASE}/api/auth/login`,
        method: 'POST',
        header: { 'content-type': 'application/x-www-form-urlencoded' },
        data: { username, password },
        success(res) {
          if (res.statusCode !== 200) return reject(new Error('用户名或密码错误'));
          wx.setStorageSync('token', res.data.access_token);
          resolve(res.data);
        },
        fail: reject,
      });
    });
  },
  logout() {
    wx.removeStorageSync('token');
    wx.redirectTo({ url: '/pages/login/login' });
  },
};
