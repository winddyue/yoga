// API 客户端：指向 FastAPI 后端，JWT 登录态复用（与 Web 版同一套接口）
// 使用前在下方修改 BASE 为后端地址；生产环境必须用 HTTPS 域名并完成 ICP 备案
const BASE = 'http://127.0.0.1:8000';

// 请求超时（毫秒）：超时按网络错误处理，避免"看起来成功实际没结果"
const TIMEOUT = 15000;

// 显式退出标记：用户主动点了「退出登录」后写入。
// 没有它的话，token 一清，onLaunch 的静默续期又会拿微信绑定把人登回来，
// 「退出登录」就形同虚设。只有用户再次主动登录才清除该标记。
const LOGOUT_FLAG = 'EXPLICIT_LOGOUT';

function markLoggedIn() {
  try { wx.removeStorageSync(LOGOUT_FLAG); } catch (e) {}
}

function isLoggedOut() {
  try { return String(wx.getStorageSync(LOGOUT_FLAG)) === '1'; } catch (e) { return false; }
}

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

// 当前运行环境：develop=开发者工具/真机调试，trial=体验版，release=正式版
function envVersion() {
  try {
    const info = wx.getAccountInfoSync && wx.getAccountInfoSync();
    return (info && info.miniProgram && info.miniProgram.envVersion) || '';
  } catch (e) {
    return '';
  }
}

// 本地模拟开关。取值优先级：
//   storage 显式设 '0' → 关；显式设 '1' → 开；
//   未设置 → 开发版（开发者工具）默认开，体验版/正式版默认关。
// 早期版本要求手工往 storage 里塞 '1'，结果手工点「微信一键登录」必然报
// "服务器未配置微信 AppID/Secret"，非常容易误判成配置缺失——改为按环境自动判定。
function devWxMock() {
  try {
    const flag = String(wx.getStorageSync(WX_MOCK_FLAG));
    if (flag === '1') return true;
    if (flag === '0') return false;
    return envVersion() === 'develop';
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
          markLoggedIn();
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
    if (res && res.access_token) { wx.setStorageSync('token', res.access_token); markLoggedIn(); }
    return res;
  },
  // 微信免密登录：wx.login 的 code 换 JWT（需后端已配置 WX_APPID/WX_SECRET，
  // 或本地联调时后端开 WX_DEV_MOCK=true）
  async wxLogin() {
    const code = await getWxCode();
    const res = await req('/api/auth/wx-login', { method: 'POST', data: { code } });
    wx.setStorageSync('token', res.access_token);
    markLoggedIn();   // 用户主动登录：清除"已退出"标记，恢复静默续期
    return res;
  },
  // 静默续期：用 wx.login 免密换一个新 token。
  // 小程序不该让用户频繁掉线——只要微信绑定还在，启动/切前台时无感刷新登录态。
  // 返回 true 表示已恢复登录，false 表示需要用户手动登录（未绑定或换设备）。
  async silentRenew() {
    try {
      const res = await this.wxLogin();
      const user = await this.get('/api/auth/me');
      const app = getApp();
      if (app) {
        app.globalData.user = user;
        app.globalData.clientId = user.client_id || null;
      }
      return true;
    } catch (e) {
      return false; // 未绑定微信等，交由页面展示未登录态
    }
  },
  // 绑定微信：登录态下把当前账号与微信关联（绑定后可免密登录）
  async wxBind() {
    const code = await getWxCode();
    return req('/api/auth/wx-bind', { method: 'POST', data: { code } });
  },
  // 微信一键注册：新用户填姓名（手机号可选）即建档并绑定微信，返回 token。
  // 已绑定过的微信会直接返回 token，重复调用不会重复建档。
  async wxRegister(name, phone) {
    const code = await getWxCode();
    const res = await req('/api/auth/wx-register', {
      method: 'POST',
      data: { code, name: name || '', phone: phone || '' },
    });
    if (res && res.access_token) { wx.setStorageSync('token', res.access_token); markLoggedIn(); }
    return res;
  },
  // 退出登录：清 token 与全局用户，回到首页（首页会展示未登录态）。
  // 同时写入"显式退出"标记，阻止下次启动时被静默续期自动登回。
  logout() {
    wx.removeStorageSync('token');
    try { wx.setStorageSync(LOGOUT_FLAG, '1'); } catch (e) {}
    const app = getApp();
    if (app) app.globalData.user = null;
    wx.switchTab({ url: '/pages/index/index' });
  },

  // 供 app.js 判断：用户是否主动退出过（此时不做静默续期）
  isLoggedOut,
};
