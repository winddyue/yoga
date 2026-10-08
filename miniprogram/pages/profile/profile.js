const api = require('../../api.js');
const { syncTheme } = require('../../utils/themes.js');

// 健身目标：与后端 ClientIn.goal 默认值保持一致，用 picker 避免手输出现脏数据
const GOALS = ['减脂', '塑形', '增肌', '理疗康复', '提升柔韧'];

Page({
  data: {
    goals: GOALS,
    profile: null,
    form: { name: '', phone: '', goal: '' },
    loading: true,
    loadErr: '',
    needLogin: false,
    saving: false,
  },

  onShow() { syncTheme(this); this.load(); },

  async load() {
    this.setData({ loading: true, loadErr: '', needLogin: false });
    const user = await getApp().ensureUser();
    if (!user) {
      this.setData({ loading: false, needLogin: true });
      return;
    }
    try {
      const p = await api.get('/api/clients/mine');
      this.setData({
        profile: p,
        form: { name: p.name || '', phone: p.phone || '', goal: p.goal || GOALS[0] },
        loading: false,
      });
    } catch (e) {
      if (e.message === '未登录') {
        this.setData({ loading: false, needLogin: true });
        return;
      }
      this.setData({ loading: false, loadErr: e.message });
    }
  },

  onInput(e) {
    const k = e.currentTarget.dataset.k;
    this.setData({ [`form.${k}`]: e.detail.value });
  },

  onGoalChange(e) {
    this.setData({ 'form.goal': this.data.goals[e.detail.value] });
  },

  async save() {
    const f = this.data.form;
    if (!f.name.trim()) {
      wx.showToast({ title: '请填写姓名', icon: 'none' });
      return;
    }
    if (f.phone && !/^1[3-9]\d{9}$/.test(f.phone)) {
      wx.showToast({ title: '手机号格式不正确', icon: 'none' });
      return;
    }
    this.setData({ saving: true });
    try {
      await api.put('/api/me/data', {
        name: f.name.trim(),
        phone: f.phone.trim(),
        goal: f.goal,
      });
      wx.showToast({ title: '已保存', icon: 'success' });
      await this.load();
    } catch (e) {
      wx.showToast({ title: e.message || '保存失败', icon: 'none' });
    } finally {
      this.setData({ saving: false });
    }
  },

  // 用户权利：查看/导出个人数据（隐私政策中承诺的能力，必须有入口）
  async exportData() {
    try {
      const d = await api.get('/api/me/data');
      const summary = [
        `姓名：${d.profile.name}`,
        `手机号：${d.profile.phone || '未填写'}`,
        `目标：${d.profile.goal}`,
        `体测记录：${d.assessments.length} 条`,
        `训练计划：${d.plans} 份`,
        `饮食方案：${d.diets} 份`,
        `约课记录：${d.bookings.length} 条`,
      ].join('\n');
      wx.showModal({
        title: '我的数据',
        content: summary,
        confirmText: '复制',
        success: (r) => {
          if (r.confirm) {
            wx.setClipboardData({ data: JSON.stringify(d, null, 2) });
          }
        },
      });
    } catch (e) {
      wx.showToast({ title: e.message || '导出失败', icon: 'none' });
    }
  },

  // 用户权利：注销账号（停用登录，数据按法规要求保留备查）
  deactivate() {
    wx.showModal({
      title: '注销账号',
      content: '注销后无法登录本小程序。按相关法规要求，馆方仍需保留你的课程与消费记录备查。确定注销？',
      confirmColor: '#c44f4f',
      success: async (r) => {
        if (!r.confirm) return;
        try {
          await api.post('/api/me/deactivate');
          wx.showToast({ title: '已注销', icon: 'success' });
          setTimeout(() => api.logout(), 800);
        } catch (e) {
          wx.showToast({ title: e.message || '注销失败', icon: 'none' });
        }
      },
    });
  },

  openAgreement() { wx.navigateTo({ url: '/pages/agreement/agreement' }); },
  goLogin() { wx.navigateTo({ url: '/pages/auth/auth' }); },
});
