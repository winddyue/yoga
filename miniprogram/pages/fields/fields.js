// 自定义字段（仅馆主）：客户档案 / 评估记录两类
const api = require('../../api.js');
const { syncTheme } = require('../../utils/themes.js');
const fb = require('../../utils/feedback.js');

const TYPES = [
  { id: 'text', name: '文本' },
  { id: 'number', name: '数字' },
  { id: 'select', name: '选项' },
];
const TARGETS = [
  { id: 'client', name: '客户档案' },
  { id: 'assessment', name: '评估记录' },
];
const TYPE_LABEL = { text: '文本', number: '数字', select: '选项' };
const TARGET_LABEL = { client: '客户档案', assessment: '评估记录' };

Page({
  data: {
    theme: 'g', fields: [], loading: true, loadErr: '',
    showForm: false, name: '', typeIdx: 0, targetIdx: 1,
    types: TYPES, targets: TARGETS,
    submitting: false,
  },

  onShow() {
    syncTheme(this);
    this.init();
  },

  async init() {
    const user = await getApp().ensureUser();
    if (!user || user.role !== 'owner') {
      fb.showError(new Error('仅馆主可管理自定义字段'));
      setTimeout(() => wx.navigateBack(), 900);
      return;
    }
    this.load();
  },

  async load() {
    this.setData({ loading: true, loadErr: '' });
    try {
      const fields = await api.get('/api/custom-fields');
      this.setData({ fields: fields || [], loading: false });
    } catch (e) {
      this.setData({ loading: false, loadErr: e.message });
    }
  },

  typeLabel(t) { return TYPE_LABEL[t] || t; },
  targetLabel(t) { return TARGET_LABEL[t] || t; },

  toggleForm() { this.setData({ showForm: !this.data.showForm }); },
  onInput(e) { this.setData({ [e.currentTarget.dataset.k]: e.detail.value }); },
  onType(e) { this.setData({ typeIdx: Number(e.detail.value) }); },
  onTarget(e) { this.setData({ targetIdx: Number(e.detail.value) }); },

  async submit() {
    const d = this.data;
    if (!String(d.name).trim()) { fb.showError(new Error('请填写字段名称')); return; }
    this.setData({ submitting: true });
    try {
      await fb.withFeedback(
        api.post('/api/custom-fields', {
          name: String(d.name).trim(),
          field_type: TYPES[d.typeIdx].id,
          target: TARGETS[d.targetIdx].id,
        }),
        { loading: '添加中…', success: '字段已添加' },
      );
      this.setData({ showForm: false, name: '', typeIdx: 0, targetIdx: 1 });
      this.load();
    } catch (e) { /* withFeedback 已提示 */ }
    this.setData({ submitting: false });
  },

  async remove(e) {
    const id = e.currentTarget.dataset.id;
    const item = this.data.fields.find((f) => f.id === id);
    const ok = await fb.confirm(`确定删除自定义字段「${item ? item.name : ''}」吗？`);
    if (!ok) return;
    try {
      await fb.withFeedback(api.del(`/api/custom-fields/${id}`), { loading: '删除中…', success: '已删除' });
      this.load();
    } catch (err) { /* withFeedback 已提示 */ }
  },
});
