// 教练代录体测（工作人员）：表单同客户自助录入。
// 注意：后端 require_sensitive_consent 按客户维度校验同意记录，与录入人无关；
// 若客户尚未授权，工作人员可代客户登记（POST /api/consents）。
const api = require('../../api.js');
const { syncTheme } = require('../../utils/themes.js');
const fb = require('../../utils/feedback.js');

function todayStr() {
  const d = new Date();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${d.getFullYear()}-${m}-${day}`;
}

Page({
  data: {
    theme: '', clientId: null, clientName: '',
    date: todayStr(), weight: '', bodyFat: '', waist: '', hip: '', notes: '',
    needLogin: false, loading: true, loadErr: '',
    needConsent: false, agreeing: false, submitting: false,
  },

  onLoad(options) {
    this.setData({ clientId: options.clientId ? Number(options.clientId) : null });
  },

  onShow() { syncTheme(this); this.init(); },

  async init() {
    const user = await getApp().ensureUser();
    if (!user) {
      this.setData({ loading: false, needLogin: true });
      return;
    }
    if (user.role !== 'coach' && user.role !== 'owner') {
      fb.showError({ message: '无权限，仅工作人员可代录' });
      setTimeout(() => wx.navigateBack(), 900);
      return;
    }
    if (!this.data.clientId) {
      this.setData({ loading: false, loadErr: '缺少客户 id' });
      return;
    }
    try {
      const c = await api.get(`/api/clients/${this.data.clientId}`);
      this.setData({ clientName: c.name || '', loading: false });
    } catch (e) {
      const expired = e.message === '未登录';
      this.setData({ loading: false, loadErr: expired ? '' : e.message, needLogin: expired });
    }
  },

  goLogin() { wx.navigateTo({ url: '/pages/auth/auth' }); },

  onDateChange(e) { this.setData({ date: e.detail.value }); },

  onInput(e) { this.setData({ [e.currentTarget.dataset.k]: e.detail.value }); },

  // 代客户登记敏感信息单独授权（工作人员可代登记）
  async agreeConsent() {
    if (this.data.agreeing || !this.data.clientId) return;
    this.setData({ agreeing: true });
    try {
      await api.post('/api/consents', {
        client_id: this.data.clientId,
        consent_type: 'sensitive_info',
        version: 'v1',
      });
      this.setData({ needConsent: false });
      fb.showSuccess('已代客户登记授权');
    } catch (e) {
      fb.showError(e, '登记失败');
    } finally {
      this.setData({ agreeing: false });
    }
  },

  _num(v) {
    if (v === '' || v === undefined || v === null) return 0;
    const n = parseFloat(v);
    return isNaN(n) ? NaN : n;
  },

  async submit() {
    if (this.data.submitting) return;
    const w = this._num(this.data.weight);
    if (isNaN(w) || w <= 0) {
      wx.showToast({ title: '请填写有效的体重', icon: 'none' });
      return;
    }
    for (const [k, label] of [['bodyFat', '体脂率'], ['waist', '腰围'], ['hip', '臀围']]) {
      const n = this._num(this.data[k]);
      if (isNaN(n) || n < 0) {
        wx.showToast({ title: `${label}请填写有效数字`, icon: 'none' });
        return;
      }
    }
    if (this.data.needConsent) {
      wx.showToast({ title: '请先完成上方的授权登记', icon: 'none' });
      return;
    }
    this.setData({ submitting: true });
    try {
      const body = {
        date: this.data.date,
        weight_kg: w,
        body_fat_pct: this._num(this.data.bodyFat),
        waist_cm: this._num(this.data.waist),
        hip_cm: this._num(this.data.hip),
      };
      if (this.data.notes) body.custom_values = { notes: this.data.notes };
      await fb.withFeedback(
        api.post(`/api/clients/${this.data.clientId}/assessments`, body),
        { loading: '保存中…', success: '代录成功' },
      );
      setTimeout(() => wx.navigateBack(), 1200);
    } catch (e) {
      if (e.message && e.message.indexOf('单独授权') >= 0) {
        this.setData({ needConsent: true });
        wx.showToast({ title: '该客户尚未授权，可代为登记', icon: 'none', duration: 2600 });
      } else {
        fb.showError(e, '保存失败');
      }
    } finally {
      this.setData({ submitting: false });
    }
  },
});
