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
    date: todayStr(),
    // 身体成分
    height: '', weight: '', bodyFat: '', muscle: '', visceral: '', bmiText: '',
    // 围度
    chest: '', waist: '', hip: '', arm: '', thigh: '',
    // 健康指标
    restingHr: '', bloodPressure: '', injuries: '', notes: '',
    // 自定义字段（target=assessment，馆主维护）：[{id, name, field_type, val}]
    cfFields: [],
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
      // 身高从客户档案预填（仅用于当场算 BMI，不回写）
      const patch = { clientName: c.name || '', loading: false };
      if (c.height_cm && c.height_cm > 0) patch.height = String(c.height_cm);
      // 自定义字段（评估类）
      try {
        const all = await api.get('/api/custom-fields');
        patch.cfFields = (all || []).filter((f) => f.target === 'assessment')
          .map((f) => ({ id: f.id, name: f.name, field_type: f.field_type, val: '' }));
      } catch (e) {}
      this.setData(patch, () => this._calcBmi());
    } catch (e) {
      const expired = e.message === '未登录';
      this.setData({ loading: false, loadErr: expired ? '' : e.message, needLogin: expired });
    }
  },

  goLogin() { wx.navigateTo({ url: '/pages/auth/auth' }); },

  onDateChange(e) { this.setData({ date: e.detail.value }); },

  onInput(e) {
    const k = e.currentTarget.dataset.k;
    this.setData({ [k]: e.detail.value }, () => {
      if (k === 'weight' || k === 'height') this._calcBmi();
    });
  },

  // 自定义字段输入（按下标更新，避免动态 key 绑定问题）
  onCfInput(e) {
    const i = Number(e.currentTarget.dataset.i);
    this.setData({ [`cfFields[${i}].val`]: e.detail.value });
  },

  // BMI = 体重kg / (身高m)^2，保留1位；身高或体重缺失时不显示
  _calcBmi() {
    const w = this._num(this.data.weight);
    const h = this._num(this.data.height);
    let t = '';
    if (!isNaN(w) && w > 0 && !isNaN(h) && h > 0) {
      t = (w / Math.pow(h / 100, 2)).toFixed(1);
    }
    this.setData({ bmiText: t });
  },

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
    // 其余数字项：填了就必须有效；必填只有体重
    for (const [k, label] of [['height', '身高'], ['bodyFat', '体脂率'], ['muscle', '肌肉量'],
        ['visceral', '内脏脂肪等级'], ['chest', '胸围'], ['waist', '腰围'], ['hip', '臀围'],
        ['arm', '上臂围'], ['thigh', '大腿围'], ['restingHr', '静息心率']]) {
      const raw = this.data[k];
      if (raw !== '' && raw !== undefined && raw !== null) {
        const n = this._num(raw);
        if (isNaN(n) || n < 0) {
          wx.showToast({ title: `${label}请填写有效数字`, icon: 'none' });
          return;
        }
      }
    }
    // 自定义字段：数字型填了必须有效
    for (const f of this.data.cfFields) {
      if (f.field_type === 'number' && f.val !== '' && f.val !== undefined && f.val !== null) {
        const n = this._num(f.val);
        if (isNaN(n) || n < 0) {
          wx.showToast({ title: `${f.name}请填写有效数字`, icon: 'none' });
          return;
        }
      }
    }
    if (this.data.needConsent) {
      wx.showToast({ title: '请先完成上方的授权登记', icon: 'none' });
      return;
    }
    this.setData({ submitting: true });
    try {
      const rh = parseInt(this._num(this.data.restingHr), 10);
      const body = {
        date: this.data.date,
        weight_kg: w,
        body_fat_pct: this._num(this.data.bodyFat),
        muscle_kg: this._num(this.data.muscle),
        bmi: this.data.bmiText ? parseFloat(this.data.bmiText) : 0,
        visceral_fat: this._num(this.data.visceral),
        chest_cm: this._num(this.data.chest),
        waist_cm: this._num(this.data.waist),
        hip_cm: this._num(this.data.hip),
        arm_cm: this._num(this.data.arm),
        thigh_cm: this._num(this.data.thigh),
        resting_hr: isNaN(rh) ? 0 : rh,
        blood_pressure: this.data.bloodPressure || '',
        injuries: this.data.injuries || '',
      };
      if (this.data.notes) body.custom_values = { notes: this.data.notes };
      // 自定义字段并入 custom_values（key 为字段 id 字符串；notes 键保留给备注）
      const cv = body.custom_values || {};
      for (const f of this.data.cfFields) {
        if (f.val !== '' && f.val !== undefined && f.val !== null) {
          cv[String(f.id)] = f.field_type === 'number' ? this._num(f.val) : f.val;
        }
      }
      if (Object.keys(cv).length) body.custom_values = cv;
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
