// 登录 / 注册页（非 tab 页）。
// 客户主路径：微信一键登录 → 未绑定则填姓名即建档（不需要密码）
// 工作人员路径：账号密码登录（教练/馆主账号由馆主在管理端创建）
const api = require('../../api.js');
const fb = require('../../utils/feedback.js');

Page({
  data: {
    username: '',
    password: '',
    name: '',
    phone: '',
    err: '',
    loading: false,
    agreed: false,      // 协议必须勾选才可登录
    step: 'main',       // main=登录首页 | profile=新用户补全资料
  },

  onInput(e) {
    this.setData({ [e.currentTarget.dataset.k]: e.detail.value });
  },

  toggleAgree() { this.setData({ agreed: !this.data.agreed }); },

  openAgreement(e) {
    const t = (e && e.currentTarget.dataset.t) || 'privacy';
    wx.navigateTo({ url: `/pages/agreement/agreement?tab=${t}` });
  },

  async afterLogin(user) {
    const app = getApp();
    app.setUser(user || await api.get('/api/auth/me'));
    fb.showSuccess('登录成功');
    wx.switchTab({ url: '/pages/index/index' });
  },

  // 微信一键登录：已绑定直接进；未绑定则进入补全资料（填姓名）
  async doWxLogin() {
    if (!this.data.agreed) {
      this.setData({ err: '请先阅读并同意《用户协议》和《隐私政策》' });
      return;
    }
    this.setData({ loading: true, err: '' });
    try {
      await api.wxLogin();
      await this.afterLogin();
    } catch (e) {
      // 404 = 该微信还没绑过账号，转入极简建档
      if (e.message && e.message.indexOf('尚未绑定') >= 0) {
        this.setData({ loading: false, step: 'profile', err: '' });
      } else {
        this.setData({ loading: false, err: e.message });
      }
    }
  },

  // 新用户：填姓名（手机号可选）后建档并绑定微信，之后即可一键登录
  async doWxRegister() {
    const name = (this.data.name || '').trim();
    if (!name) { this.setData({ err: '请填写姓名，便于课堂点名' }); return; }
    const phone = (this.data.phone || '').trim();
    if (phone && !/^1\d{10}$/.test(phone)) {
      this.setData({ err: '手机号格式不正确' });
      return;
    }
    this.setData({ loading: true, err: '' });
    try {
      await api.wxRegister(name, phone);
      await this.afterLogin();
    } catch (e) {
      this.setData({ loading: false, err: e.message });
    }
  },

  // 账号密码登录（教练/馆主，或已有账号的客户）
  async doPwdLogin() {
    if (!this.data.agreed) {
      this.setData({ err: '请先阅读并同意《用户协议》和《隐私政策》' });
      return;
    }
    const { username, password } = this.data;
    if (!username || !password) { this.setData({ err: '请输入用户名和密码' }); return; }
    this.setData({ loading: true, err: '' });
    try {
      await fb.withFeedback(api.login(username, password), { loading: '登录中…' });
      api.wxBind().catch(() => {});   // 静默绑定微信，失败不影响登录
      await this.afterLogin();
    } catch (e) {
      this.setData({ err: e.message });
    } finally {
      this.setData({ loading: false });
    }
  },

  backToMain() { this.setData({ step: 'main', err: '' }); },

  // 返回：非 tab 页，直接返回上一页；无上一页时回首页
  back() {
    const pages = getCurrentPages();
    if (pages.length > 1) wx.navigateBack();
    else wx.switchTab({ url: '/pages/index/index' });
  },
});
