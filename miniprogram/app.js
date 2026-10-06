// 小程序入口：全局 API 客户端与登录态管理（脚手架）
const api = require('./api.js');

App({
  globalData: {
    user: null,      // {id, username, role, name}
    clientId: null,  // 客户角色绑定的客户档案 id（后端解析）
  },
  onLaunch() {
    const token = wx.getStorageSync('token');
    if (token) {
      api.get('/api/auth/me').then((user) => {
        this.globalData.user = user;
      }).catch(() => wx.removeStorageSync('token'));
    }
  },
});
