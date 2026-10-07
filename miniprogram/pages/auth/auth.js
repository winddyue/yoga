// 登录 / 注册页（非 tab 页）。
// 设计对齐主流小程序：默认展示「微信手机号快捷登录」+「账号密码登录」两种方式，
// 手机号授权即完成注册与登录，用户无需单独填注册表单。
const api = require('../../api.js');
const fb = require('../../utils/feedback.js');

Page({
  data: {
    mode: 'quick',      // quick=手机号快捷 | pwd=账号密码
    username: '',
    password: '',
    name: '',
    code: '',           // 手机号授权 code（真机由 getPhoneNumber 提供）
    phone: '',          // mock/手填的手机号
    err: '',
    loading: false,
    agreed: true,       // 是否同意协议
  },

  onInput(e) {
    this.setData({ [e.currentTarget.dataset.k]: e.detail.value });
  },

  switchMode(e) {
    this.setData({ mode: e.currentTarget.dataset.m, err: '' });
  },

  toggleAgree() { this.setData({ agreed: !this.data.agreed }); },

  // 授权后统一入口：拿到 token 即算登录成功
  async afterLogin(user) {
    const app = getApp();
    app.globalData.user = user || await api.get('/api/auth/me');
    fb.showSuccess('登录成功');
    wx.switchTab({ url: '/pages/index/index' });
  },

  // 手机号快捷登录/注册
  // 真机：<button open-type="getPhoneNumber" bindgetphonenumber="onGetPhone">
  // 开发者工具不支持该授权，可展开"模拟手机号"手输一个号码联调
  async onGetPhone(e) {
    if (!this.data.agreed) { this.setData({ err: '请先阅读并同意用户协议和隐私政策' }); return; }
    const code = (e && e.detail && e.detail.code) || '';
    const phone = (this.data.phone || '').trim();
    if (!code && !phone) {
      this.setData({ err: '未获取到手机号，请重试或使用账号密码登录' });
      return;
    }
    this.setData({ loading: true, err: '' });
    try {
      // 工具里没有真实 code 时，用 mock:手机号 走后端开发模式
      const payload = code || ('mock:' + phone);
      await api.phoneRegister(payload, this.data.name);
      await this.afterLogin();
    } catch (err) {
      this.setData({ err: err.message });
    } finally {
      this.setData({ loading: false });
    }
  },

  // 账号密码登录（教练/馆主与已有客户账号）
  async doPwdLogin() {
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

  // 返回：非 tab 页，直接返回上一页；无上一页时回首页
  back() {
    const pages = getCurrentPages();
    if (pages.length > 1) wx.navigateBack();
    else wx.switchTab({ url: '/pages/index/index' });
  },
});
