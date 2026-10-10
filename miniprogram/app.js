// 小程序入口：全局 API 客户端与登录态管理
const api = require('./api.js');

App({
  globalData: {
    user: null,      // {id, username, role, name, client_id}
    clientId: null,  // 客户角色绑定的客户档案 id（后端解析）
    privacyResolve: null,  // 微信隐私授权回调，等待用户点「同意」
  },

  // 登录态解析结果缓存：页面共用同一个 Promise，避免并发重复请求与状态竞态。
  // 用 token 作为失效依据——token 变了（过期被清、续期换新、退出登录）就重新解析，
  // 否则游客态会被永久缓存，静默续期再也不会触发。
  _userPromise: null,
  _resolvedToken: undefined,

  onLaunch() {
    this.ensureUser();
    this._setupPrivacy();
  },

  /**
   * 隐私授权：公众平台配置《用户隐私保护指引》后，微信会拦截相册/相机等接口，
   * 调用前必须由用户点「同意」。这里保存微信给的 resolve，
   * 由页面上的 privacy-popup 组件弹窗承接（见 components/privacy）。
   * 未配置隐私指引时该回调不会触发，不影响现有功能。
   */
  _setupPrivacy() {
    if (!wx.onNeedPrivacyAuthorization) return;
    wx.onNeedPrivacyAuthorization((resolve) => {
      this.globalData.privacyResolve = resolve;
      if (this._privacyHandler) this._privacyHandler();
    });
  },

  // 组件挂载时注册唤醒回调；若已有待处理的授权请求，立即弹窗
  registerPrivacyHandler(fn) {
    this._privacyHandler = fn;
    if (this.globalData.privacyResolve) fn();
  },

  /**
   * 解析当前登录态，返回 user 或 null。
   * 顺序：本地 token → 静默续期（wx.login 免密换 token）→ 放弃（游客）
   * 小程序场景不该让用户频繁掉线：token 过期时用微信绑定无感恢复。
   */
  ensureUser() {
    const token = wx.getStorageSync('token') || '';
    if (this._userPromise && this._resolvedToken === token) {
      return this._userPromise;
    }
    this._resolvedToken = token;
    this._userPromise = this._resolveUser().then((user) => {
      this.globalData.user = user;
      this.globalData.clientId = user ? (user.client_id || null) : null;
      // 续期会换发新 token，同步缓存键，避免下次又重复解析
      this._resolvedToken = wx.getStorageSync('token') || '';
      return user;
    });
    return this._userPromise;
  },

  async _resolveUser() {
    // 1. 已有 token：直接取用户信息
    if (wx.getStorageSync('token')) {
      try {
        return await api.get('/api/auth/me');
      } catch (e) {
        // token 过期或失效，继续尝试续期
      }
    }
    // 2. 无 token 或已失效：用 wx.login 静默换 token（用户无感知）
    //    例外：用户主动点过「退出登录」就不再自动登回，否则退出按钮毫无意义
    if (api.isLoggedOut && api.isLoggedOut()) return null;
    try {
      const renewed = await api.silentRenew();
      if (renewed) {
        const app = getApp();
        return app ? app.globalData.user : null;
      }
    } catch (e) {
      // 续期失败，落到游客态
    }
    return null;
  },

  // 登录成功后调用：写入用户信息并重置缓存，使后续 await 拿到最新状态
  setUser(user) {
    this.globalData.user = user;
    this.globalData.clientId = user ? (user.client_id || null) : null;
    this._resolvedToken = wx.getStorageSync('token') || '';
    this._userPromise = Promise.resolve(user);
  },

  // 退出登录后调用：清空登录态与缓存
  clearUser() {
    this.globalData.user = null;
    this.globalData.clientId = null;
    this._resolvedToken = wx.getStorageSync('token') || '';
    this._userPromise = Promise.resolve(null);
  },
});
