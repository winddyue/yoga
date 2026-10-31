// 订阅套餐管理（仅馆主）：套餐列表 / 新增 / 编辑 / 上下架
const api = require('../../api.js');
const { syncTheme } = require('../../utils/themes.js');
const fb = require('../../utils/feedback.js');
const { fmtYuan } = require('../../utils/money.js');

const emptyForm = () => ({ id: null, name: '', price: '', days: '', desc: '' });

Page({
  data: {
    plans: [], loading: true, loadErr: '',
    showForm: false, submitting: false,
    form: emptyForm(),
  },

  onShow() { syncTheme(this); this.init(); },

  async init() {
    const user = await getApp().ensureUser();
    if (!user || user.role !== 'owner') {
      fb.showError(new Error('仅馆主可管理订阅套餐'));
      setTimeout(() => wx.navigateBack(), 900);
      return;
    }
    this.load();
  },

  async load() {
    this.setData({ loading: true, loadErr: '' });
    try {
      const plans = await api.get('/api/products?all=true');
      this.setData({
        plans: (plans || []).map((p) => ({ ...p, priceText: fmtYuan(p.price_cents) })),
        loading: false,
      });
    } catch (e) {
      this.setData({ loadErr: (e && e.message) || '加载失败', loading: false });
    }
  },

  toggleForm() {
    this.setData({ showForm: !this.data.showForm, form: emptyForm() });
  },

  cancelEdit() {
    this.setData({ showForm: false, form: emptyForm() });
  },

  onInput(e) {
    const k = e.currentTarget.dataset.k;
    this.setData({ [`form.${k}`]: e.detail.value });
  },

  edit(e) {
    const p = this.data.plans.find((x) => String(x.id) === String(e.currentTarget.dataset.id));
    if (!p) return;
    this.setData({
      showForm: true,
      form: {
        id: p.id,
        name: p.name || '',
        price: (Number(p.price_cents) / 100).toFixed(2),
        days: String(p.duration_days || ''),
        desc: p.description || '',
      },
    });
  },

  async submit() {
    const f = this.data.form;
    const name = (f.name || '').trim();
    const priceYuan = parseFloat(f.price);
    const days = parseInt(f.days, 10);
    if (!name) return fb.showError(new Error('请填写套餐名称'));
    if (!(priceYuan > 0)) return fb.showError(new Error('请填写有效价格（元）'));
    if (!(days > 0)) return fb.showError(new Error('请填写有效天数'));
    const body = {
      name,
      price_cents: Math.round(priceYuan * 100),
      duration_days: days,
      description: (f.desc || '').trim(),
    };
    this.setData({ submitting: true });
    try {
      if (f.id) await api.patch(`/api/products/${f.id}`, body);
      else await api.post('/api/products', body);
      fb.showSuccess(f.id ? '已保存' : '已新增');
      this.setData({ showForm: false, submitting: false, form: emptyForm() });
      this.load();
    } catch (e) {
      this.setData({ submitting: false });
      fb.showError(e); // 含 403"仅馆主可操作"
    }
  },

  async toggleActive(e) {
    const p = this.data.plans.find((x) => String(x.id) === String(e.currentTarget.dataset.id));
    if (!p) return;
    const action = p.active ? '下架' : '上架';
    const ok = await fb.confirm(`确定${action}「${p.name}」？${p.active ? '下架后学员将看不到该套餐。' : ''}`, action);
    if (!ok) return;
    try {
      await fb.withFeedback(api.patch(`/api/products/${p.id}`, { active: !p.active }), { loading: `${action}中…` });
      this.load();
    } catch (err) { fb.showError(err); }
  },
});
