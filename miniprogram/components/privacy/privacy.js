// 隐私授权弹窗
//
// 背景：app.json 开了 "__usePrivacyCheck__"，一旦在公众平台配置了《用户隐私保护指引》，
// 微信会拦截相册/相机（wx.chooseMedia）等隐私接口——调用前必须让用户点「同意」，
// 否则接口直接失败，表现为「点拍照没反应」。
//
// 用法：页面 wxml 里放一行 <privacy-popup />（组件已在 app.json 全局注册，
// 无需各页面再声明）。授权请求由 app.js 的 onNeedPrivacyAuthorization 转发过来。
Component({
  data: {
    show: false,
  },

  lifetimes: {
    attached() {
      // getApp() 只能在运行时调用，不能写在文件顶层
      const app = getApp();
      if (app && typeof app.registerPrivacyHandler === 'function') {
        app.registerPrivacyHandler(() => this.setData({ show: true }));
      }
    },
  },

  methods: {
    // 微信要求：同意必须由用户点击 open-type="agreePrivacyAuthorization" 的按钮触发
    onAgree() {
      this._resolve({ buttonId: 'agree-btn', event: 'agree' });
    },

    onDisagree() {
      this._resolve({ event: 'disagree' });
    },

    _resolve(payload) {
      const app = getApp();
      const resolve = app && app.globalData && app.globalData.privacyResolve;
      if (resolve) {
        try {
          resolve(payload);
        } catch (e) {
          // 已 resolve 过再调用会抛错，忽略即可
        }
        app.globalData.privacyResolve = null;
      }
      this.setData({ show: false });
    },

    openPrivacy() {
      wx.navigateTo({ url: '/pages/agreement/agreement?tab=privacy' });
    },

    // 弹窗期间阻止页面滚动穿透
    noop() {},
  },
});
