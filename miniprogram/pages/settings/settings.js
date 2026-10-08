// 系统设置（仅馆主）：AI/OCR/ASR 接口配置
const api = require('../../api.js');
const { syncTheme } = require('../../utils/themes.js');
const fb = require('../../utils/feedback.js');

const VERSION = 'v7.2';

Page({
  data: {
    theme: 'g', loading: true, loadErr: '',
    ai_api_url: '', ai_model: '', ocr_api_url: '', asr_api_url: '',
    ai_enabled: false,
    ai_configured: false, ocr_configured: false, asr_configured: false,
    saving: false, version: VERSION,
  },

  onShow() {
    syncTheme(this);
    this.init();
  },

  async init() {
    const user = await getApp().ensureUser();
    if (!user || user.role !== 'owner') {
      fb.showError(new Error('仅馆主可修改设置'));
      setTimeout(() => wx.navigateBack(), 900);
      return;
    }
    this.load();
  },

  async load() {
    this.setData({ loading: true, loadErr: '' });
    try {
      const s = await api.get('/api/settings');
      this.setData({
        ai_api_url: s.ai_api_url || '', ai_model: s.ai_model || '',
        ocr_api_url: s.ocr_api_url || '', asr_api_url: s.asr_api_url || '',
        ai_enabled: !!s.ai_enabled,
        ai_configured: !!s.ai_configured, ocr_configured: !!s.ocr_configured, asr_configured: !!s.asr_configured,
        loading: false,
      });
    } catch (e) {
      this.setData({ loading: false, loadErr: e.message });
    }
  },

  onInput(e) { this.setData({ [e.currentTarget.dataset.k]: e.detail.value }); },
  onSwitch(e) { this.setData({ ai_enabled: e.detail.value }); },
  goTheme() { wx.navigateTo({ url: '/pages/theme/theme' }); },

  async save() {
    const d = this.data;
    this.setData({ saving: true });
    try {
      await fb.withFeedback(
        api.put('/api/settings', {
          ai_api_url: d.ai_api_url.trim(), ai_model: d.ai_model.trim(),
          ocr_api_url: d.ocr_api_url.trim(), asr_api_url: d.asr_api_url.trim(),
          ai_enabled: d.ai_enabled,
        }),
        { loading: '保存中…', success: '设置已保存' },
      );
      this.load();
    } catch (e) { /* withFeedback 已提示 */ }
    this.setData({ saving: false });
  },
});
