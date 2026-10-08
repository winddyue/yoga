// 智能录入：文字 / 拍照 → AI 提取 → 人工确认 → 入库（馆主/教练）
// 拍照走 /api/ocr-extract（后端占位，未配置返回 501）；语音暂不做
const api = require('../../api.js');
const { syncTheme } = require('../../utils/themes.js');
const fb = require('../../utils/feedback.js');

const EDITABLE = [
  { k: 'weight_kg', label: '体重', unit: 'kg' },
  { k: 'body_fat_pct', label: '体脂率', unit: '%' },
  { k: 'muscle_kg', label: '肌肉量', unit: 'kg' },
  { k: 'waist_cm', label: '腰围', unit: 'cm' },
  { k: 'hip_cm', label: '臀围', unit: 'cm' },
  { k: 'height_cm', label: '身高', unit: 'cm' },
  { k: 'age', label: '年龄', unit: '岁' },
];

Page({
  data: {
    theme: 'g', tab: 'text',
    clientId: null, clientName: '', clients: [], clientIdx: 0,
    text: '', extracting: false,
    editFields: [], // [{k,label,unit,value}]
    confirming: false, uploading: false,
    ready: false,
  },

  onLoad(opts) {
    if (opts.clientId) this.setData({ clientId: Number(opts.clientId) });
  },

  onShow() {
    syncTheme(this);
    this.init();
  },

  async init() {
    if (this.data.ready) return;
    const user = await getApp().ensureUser();
    if (!user || (user.role !== 'owner' && user.role !== 'coach')) {
      fb.showError(new Error('需要教练或馆主权限'));
      setTimeout(() => wx.navigateBack(), 900);
      return;
    }
    if (this.data.clientId) {
      try {
        const c = await api.get(`/api/clients/${this.data.clientId}`);
        this.setData({ clientName: c.name || '' });
      } catch (e) { this.setData({ clientId: null }); }
    }
    if (!this.data.clientId) {
      try {
        const list = await api.get('/api/clients');
        this.setData({ clients: list || [], clientIdx: 0 });
        if (list && list.length) this.setData({ clientId: list[0].id, clientName: list[0].name });
      } catch (e) { /* 客户列表失败不阻塞，提示选择 */ }
    }
    this.setData({ ready: true });
  },

  switchTab(e) { this.setData({ tab: e.currentTarget.dataset.t, editFields: [] }); },
  onInput(e) { this.setData({ [e.currentTarget.dataset.k]: e.detail.value }); },
  onClient(e) {
    const i = Number(e.detail.value);
    const c = this.data.clients[i];
    if (c) this.setData({ clientIdx: i, clientId: c.id, clientName: c.name, editFields: [] });
  },
  onFieldInput(e) {
    const k = e.currentTarget.dataset.k;
    this.setData({
      editFields: this.data.editFields.map((f) => (f.k === k ? { ...f, value: e.detail.value } : f)),
    });
  },

  _needClient() {
    if (!this.data.clientId) { fb.showError(new Error('请先选择客户')); return false; }
    return true;
  },

  _notConfiguredMsg(e) {
    const m = (e && e.message) || '';
    return m.indexOf('501') >= 0 || m.indexOf('配置') >= 0;
  },

  async extract() {
    if (!this._needClient()) return;
    const text = String(this.data.text).trim();
    if (!text) { fb.showError(new Error('请输入要识别的文字，如"体重68kg，体脂30%"')); return; }
    this.setData({ extracting: true });
    try {
      const r = await fb.withFeedback(api.post('/api/intake/extract', { text }), { loading: 'AI 提取中…' });
      const fields = (r && r.fields) || {};
      const editFields = EDITABLE.map((f) => ({ ...f, value: fields[f.k] != null ? String(fields[f.k]) : '' }));
      this.setData({ editFields });
      if (!Object.keys(fields).length) fb.showError(new Error('未能提取到有效字段，请换种说法试试'));
    } catch (e) {
      if (this._notConfiguredMsg(e)) fb.showError(new Error('馆主尚未配置 AI 服务，请联系馆主'));
    }
    this.setData({ extracting: false });
  },

  async choosePhoto() {
    if (!this._needClient()) return;
    let r;
    try {
      r = await wx.chooseMedia({ count: 1, mediaType: ['image'], sourceType: ['album', 'camera'] });
    } catch (e) { return; }
    if (!r || !r.tempFiles || !r.tempFiles.length) return;
    const filePath = r.tempFiles[0].tempFilePath;
    this.setData({ uploading: true });
    const token = wx.getStorageSync('token') || '';
    wx.uploadFile({
      url: api.BASE + '/api/ocr-extract',
      filePath,
      name: 'file',
      header: { Authorization: token ? `Bearer ${token}` : '' },
      success: (res) => {
        let data = null;
        try { data = JSON.parse(res.data); } catch (e) {}
        if (res.statusCode === 501) { fb.showError(new Error('馆主尚未配置 OCR，请用文字录入')); return; }
        if (res.statusCode >= 400) { fb.showError(new Error((data && data.detail) || '识别失败，请重试')); return; }
        const fields = (data && data.data) || {};
        const editFields = EDITABLE.map((f) => ({ ...f, value: fields[f.k] != null ? String(fields[f.k]) : '' }));
        this.setData({ editFields });
        if (!Object.keys(fields).length) fb.showError(new Error('未能识别出有效字段，请用文字录入'));
      },
      fail: () => fb.showError(new Error('网络连接失败，请检查网络')),
      complete: () => this.setData({ uploading: false }),
    });
  },

  async confirmSave() {
    if (!this._needClient()) return;
    const fields = {};
    this.data.editFields.forEach((f) => {
      const v = String(f.value).trim();
      if (v !== '') {
        const n = Number(v);
        fields[f.k] = Number.isNaN(n) ? v : n;
      }
    });
    if (!Object.keys(fields).length) { fb.showError(new Error('请至少填写一项数据')); return; }
    this.setData({ confirming: true });
    try {
      await fb.withFeedback(
        api.post('/api/intake/confirm', { client_id: this.data.clientId, fields }),
        { loading: '保存中…', success: '已保存为评估记录' },
      );
      this.setData({ editFields: [], text: '' });
      setTimeout(() => wx.navigateBack(), 600);
    } catch (e) {
      const m = (e && e.message) || '';
      if (m.indexOf('授权') >= 0) fb.showError(new Error('该客户尚未完成敏感信息授权，无法入库'));
    }
    this.setData({ confirming: false });
  },
});
