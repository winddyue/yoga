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

// 小程序环境没有 FormData 全局对象，必须先判断存在性再 instanceof，
// 否则直接 ReferenceError，导致所有 req() 请求失败（登录成功也无法跳转首页）
function isFormData(d) {
  return typeof FormData !== 'undefined' && d instanceof FormData;
}

function req(path, { method = 'GET', data = null } = {}) {
  return new Promise((resolve, reject) => {
    wx.request({
      url: BASE + path,
      method,
      data,
      timeout: TIMEOUT,
      header: headers(!isFormData(data)),
      success(res) {
        if (res.statusCode === 401) {
          // 未登录/登录过期：只清 token，不再强制跳登录页。
          // 小程序允许未登录浏览（主流做法：首页可直接看，需要个人信息时才引导登录），
          // 由各页面自行展示"未登录"引导态并跳转登录页。
          wx.removeStorageSync('token');
          const app = getApp();
          if (app) app.globalData.user = null;
          return reject(new Error('未登录'));
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

// ---- 开发期微信登录模拟 ----
// 开发者工具/真机没有配置 AppSecret 时，wx.login 拿到的 code 无法换 openid，
// 且该 code 每次都不同（实测 3 次 3 个值），无法模拟"同一个微信"，绑定链路走不通。
// 因此在本地 storage 里设 DEV_WX_MOCK=1 时，改用一个稳定的设备标识拼成
// "mock:xxx" 交给后端（后端需 WX_DEV_MOCK=true）。
// 生产环境用户不会设置该 storage；且后端未开 WX_DEV_MOCK 时对 mock: code 一律拒绝，双保险。
const WX_MOCK_FLAG = 'DEV_WX_MOCK';
const WX_MOCK_DID = 'DEV_WX_DID';

function devWxMock() {
  try {
    return String(wx.getStorageSync(WX_MOCK_FLAG)) === '1';
  } catch (e) {
    return false;
  }
}

// 稳定的模拟身份：首次生成后存本地，模拟"同一个微信号"反复登录
function devDeviceId() {
  try {
    let id = wx.getStorageSync(WX_MOCK_DID);
    if (!id) {
      id = 'dev-' + Math.random().toString(36).slice(2, 10);
      wx.setStorageSync(WX_MOCK_DID, id);
    }
    return id;
  } catch (e) {
    return 'dev-fallback';
  }
}

// wx.login 拿临时 code（静默，无需用户授权）
function getWxCode() {
  if (devWxMock()) {
    return Promise.resolve('mock:' + devDeviceId());
  }
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
  // 手机号授权注册/登录：getPhoneNumber 的 code 换手机号，已注册即登录。
  // name 可选（首次注册时作为姓名）；顺带带 wx.login 的 code 绑定微信实现免密登录。
  // 后端直接签发 token，拿到即视为已登录。
  async phoneRegister(phoneCode, name) {
    let wxCode = '';
    try { wxCode = await getWxCode(); } catch (e) { /* 绑定失败不影响注册 */ }
    const res = await req('/api/auth/phone-register', {
      method: 'POST',
      data: { code: phoneCode, name: name || '', wx_code: wxCode },
    });
    if (res && res.access_token) wx.setStorageSync('token', res.access_token);
    return res;
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
  // 退出登录：清 token 与全局用户，回到首页（首页会展示未登录态）
  logout() {
    wx.removeStorageSync('token');
    const app = getApp();
    if (app) app.globalData.user = null;
    wx.switchTab({ url: '/pages/index/index' });
  },
};
