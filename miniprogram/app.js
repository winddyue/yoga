// 小程序入口：全局 API 客户端与登录态管理
const api = require('./api.js');

App({
  globalData: {
    user: null,      // {id, username, role, name, client_id}
    clientId: null,  // 客户角色绑定的客户档案 id（后端解析）
  },
  onLaunch() {
    // 有 token 就静默拉取用户信息；失败（过期/无效）静默清掉，不打扰用户，
    // 页面会自行展示"未登录"引导态（首页可直接浏览，不做强制跳转）
    const token = wx.getStorageSync('token');
    if (token) {
      api.get('/api/auth/me').then((user) => {
        this.globalData.user = user;
        this.globalData.clientId = user.client_id || null;
      }).catch(() => {});
    }
  },
});
