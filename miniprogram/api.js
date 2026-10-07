// API 客户端：指向 FastAPI 后端，JWT 登录态复用（与 Web 版同一套接口）
// 使用前在下方修改 BASE 为后端地址；生产环境必须用 HTTPS 域名并完成 ICP 备案
const BASE = 'http://127.0.0.1:8000';

// 请求超时（毫秒）：超时按网络错误处理，避免"看起来成功实际没结果"
const TIMEOUT = 15000;

function headers(json = true) {
  const h = {};
  if (json) h['content-type'] = 'application/json';
  const t = wx.getStorageSync('token');
  if (t) h['Authorization'] = `Bearer ${t}`;
  return h;
}

// 网络层失败（断网/超时/DNS）→ 友好中文提示，不把原始 errMsg 甩给用户
function networkError(err) {
  const msg = (err && err.errMsg) || '';
  if (msg.indexOf('timeout') >= 0) return new Error('网络超时，请检查网络后重试');
  return new Error('网络连接失败，请检查网络');
}

function req(path, { method = 'GET', data = null } = {}) {
  return new Promise((resolve, reject) => {
    wx.request({
      url: BASE + path,
      method,
      data,
      timeout: TIMEOUT,
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
      fail: (err) => reject(networkError(err)),
    });
  });
}

// wx.login 拿临时 code（静默，无需用户授权）
function getWxCode() {
  return new Promise((resolve, reject) => {
    wx.login({
      success: (res) => (res.code ? resolve(res.code) : reject(new Error('获取微信登录凭证失败'))),
      fail: () => reject(new Error('拉起微信登录失败，请重试')),
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
        timeout: TIMEOUT,
        success(res) {
          if (res.statusCode !== 200) {
            return reject(new Error((res.data && res.data.detail) || '用户名或密码错误'));
          }
          wx.setStorageSync('token', res.data.access_token);
          resolve(res.data);
        },
        fail: (err) => reject(networkError(err)),
      });
    });
  },
  register(name, username, password) {
    return req('/api/auth/register', { method: 'POST', data: { name, username, password } });
  },
  // 微信免密登录：wx.login 的 code 换 JWT（需后端已配置 WX_APPID/WX_SECRET）
  async wxLogin() {
    const code = await getWxCode();
    const res = await req('/api/auth/wx-login', { method: 'POST', data: { code } });
    wx.setStorageSync('token', res.access_token);
    return res;
  },
  // 绑定微信：登录态下把当前账号与微信关联（绑定后可免密登录）
  async wxBind() {
    const code = await getWxCode();
    return req('/api/auth/wx-bind', { method: 'POST', data: { code } });
  },
  logout() {
    wx.removeStorageSync('token');
    wx.redirectTo({ url: '/pages/login/login' });
  },
};
