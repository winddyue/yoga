const api = require('../../api.js');
const fb = require('../../utils/feedback.js');

Page({
  data: { username: '', password: '', err: '', wxLogging: false, loading: false },

  onInput(e) { this.setData({ [e.currentTarget.dataset.k]: e.detail.value }); },

  async afterLogin() {
    const user = await api.get('/api/auth/me');
    getApp().globalData.user = user;
    fb.showSuccess('登录成功');
    wx.switchTab({ url: '/pages/index/index' });
  },

  // 账号密码登录：成功后顺手静默绑定微信（失败不打扰用户）
  async doLogin() {
    if (!this.data.username || !this.data.password) {
      this.setData({ err: '请输入用户名和密码' });
      return;
    }
    try {
      this.setData({ loading: true });
      await fb.withFeedback(
        api.login(this.data.username, this.data.password),
        { loading: '登录中…' },
      );
      api.wxBind().catch(() => {}); // 绑定失败不影响登录
      await this.afterLogin();
    } catch (e) {
      this.setData({ err: e.message });
    } finally { this.setData({ loading: false });
    }
  },

  goRegister() { wx.navigateTo({ url: '/pages/register/register' }); },

  // 微信一键登录：已绑定的微信直接换 token；未绑定则提示先密码登录
  async doWxLogin() {
    if (this.data.wxLogging) return;
    this.setData({ wxLogging: true, err: '' });
    try {
      await fb.withFeedback(api.wxLogin(), { loading: '微信登录中…' });
      await this.afterLogin();
    } catch (e) {
      if (e.message && e.message.indexOf('绑定') >= 0) {
        wx.showModal({
          title: '微信未绑定',
          content: '该微信尚未绑定账号。请先用账号密码登录，登录后将自动绑定，下次即可一键登录。',
          showCancel: false,
        });
      } else {
        this.setData({ err: e.message });
      }
    } finally {
      this.setData({ wxLogging: false });
    }
  },
});
