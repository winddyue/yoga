// 训练计划详情（客户）：按天展示动作，今日高亮
const api = require('../../api.js');
const { syncTheme } = require('../../utils/themes.js');
const fb = require('../../utils/feedback.js');

const WEEKDAYS = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];

Page({
  data: { plan: null, today: '', loading: true },

  onLoad(q) { this.pid = q.id; },

  onShow() {
    syncTheme(this);
    this.setData({ today: WEEKDAYS[new Date().getDay()] });
    this.load();
  },

  async load() {
    this.setData({ loading: true });
    const user = await getApp().ensureUser();
    if (!user) { this.setData({ loading: false }); return; }
    try {
      const c = await api.get('/api/clients/mine');
      const plans = await api.get(`/api/clients/${c.id}/plans`);
      const plan = (plans || []).find((p) => String(p.id) === String(this.pid)) || null;
      this.setData({ plan, loading: false });
    } catch (e) {
      fb.showError(e, '加载失败');
      this.setData({ loading: false });
    }
  },

  goCheckin() { wx.switchTab({ url: '/pages/training/training' }); },
});
