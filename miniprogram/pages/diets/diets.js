// 饮食方案管理（工作人员）：列表 + AI 生成初版 + 一键确认 + 餐单明细。
const api = require('../../api.js');
const { syncTheme } = require('../../utils/themes.js');
const fb = require('../../utils/feedback.js');

const MEAL_LABEL = { breakfast: '早餐', lunch: '午餐', dinner: '晚餐', snack: '加餐' };
const STATUS_TEXT = { ai_draft: 'AI 生成·待确认', pending: '待确认', confirmed: '已确认' };
const STATUS_CLS = { ai_draft: 's-waitlist', pending: 's-waitlist', confirmed: 's-checked_in' };

Page({
  data: {
    theme: '', clientId: null, clientName: '',
    diets: [], loading: true, loadErr: '', needLogin: false,
    expandedId: null, generating: false, confirmingId: null,
  },

  onLoad(options) {
    this.setData({ clientId: options.clientId ? Number(options.clientId) : null });
  },

  onShow() { syncTheme(this); this.load(); },

  async load() {
    this.setData({ loading: true, loadErr: '', needLogin: false });
    const user = await getApp().ensureUser();
    if (!user) {
      this.setData({ loading: false, needLogin: true });
      return;
    }
    if (user.role !== 'coach' && user.role !== 'owner') {
      fb.showError({ message: '无权限，仅工作人员可管理' });
      setTimeout(() => wx.navigateBack(), 900);
      return;
    }
    if (!this.data.clientId) {
      this.setData({ loading: false, loadErr: '缺少客户 id' });
      return;
    }
    try {
      const [client, diets] = await fb.withFeedback(Promise.all([
        api.get(`/api/clients/${this.data.clientId}`),
        api.get(`/api/clients/${this.data.clientId}/diets`),
      ]), { loading: '加载中…' });
      const rows = (diets || []).map((d) => {
        const meals = d.meals || {};
        const mealList = Object.keys(MEAL_LABEL)
          .filter((k) => (meals[k] || []).length)
          .map((k) => ({ label: MEAL_LABEL[k], items: meals[k].join('、') }));
        return {
          id: d.id, date: d.date || '', status: d.status,
          statusText: STATUS_TEXT[d.status] || d.status,
          statusCls: STATUS_CLS[d.status] || 's-booked',
          calories: d.calories_target || 0,
          protein: d.protein_g || 0, fat: d.fat_g || 0, carbs: d.carbs_g || 0,
          disclaimer: d.disclaimer || '', mealList,
          canConfirm: d.status === 'ai_draft' || d.status === 'pending',
        };
      });
      this.setData({ clientName: client.name || '', diets: rows, loading: false });
    } catch (e) {
      const expired = e.message === '未登录';
      this.setData({ loading: false, loadErr: expired ? '' : e.message, needLogin: expired });
    }
  },

  goLogin() { wx.navigateTo({ url: '/pages/auth/auth' }); },

  toggle(e) {
    const id = e.currentTarget.dataset.id;
    this.setData({ expandedId: this.data.expandedId === id ? null : id });
  },

  // AI 生成初版饮食方案
  async aiGenerate() {
    if (this.data.generating) return;
    this.setData({ generating: true });
    try {
      await fb.withFeedback(
        api.post(`/api/clients/${this.data.clientId}/diets/ai-generate`),
        { loading: 'AI 生成中…', success: '初版已生成' },
      );
      this.load();
    } catch (e) {
      if (e.statusCode === 503 || (e.message && e.message.indexOf('尚未配置 AI') >= 0)) {
        wx.showToast({ title: '馆主尚未配置 AI 服务', icon: 'none', duration: 2600 });
      } else {
        fb.showError(e, '生成失败');
      }
    } finally {
      this.setData({ generating: false });
    }
  },

  // 一键确认（可先在明细里微调，本期直接确认）
  async confirm(e) {
    const id = e.currentTarget.dataset.id;
    if (this.data.confirmingId) return;
    const ok = await fb.confirm('确认后该方案将推送给客户，继续？', '确认饮食方案');
    if (!ok) return;
    this.setData({ confirmingId: id });
    try {
      await fb.withFeedback(
        api.post(`/api/diets/${id}/confirm`),
        { loading: '确认中…', success: '已确认并通知客户' },
      );
      this.load();
    } catch (e) {
      fb.showError(e, '确认失败');
    } finally {
      this.setData({ confirmingId: null });
    }
  },
});
