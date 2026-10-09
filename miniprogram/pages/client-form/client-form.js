// 新增客户（工作人员）。此前 POST /api/clients 早已存在，但没有前端入口，
// 只能靠接口调，所以首页「新增客户」点不下去。此页把它补齐。
const api = require('../../api.js');
const { syncTheme } = require('../../utils/themes.js');
const fb = require('../../utils/feedback.js');

const GENDERS = ['未填写', '女', '男'];
const GOALS = ['减脂', '塑形', '增肌', '体态改善', '产后修复', '康复训练', '其他'];
const NO_COACH = '暂不分配';
const PHONE_RE = /^1\d{10}$/;

Page({
  data: {
    theme: '',
    // 表单
    name: '', genderIdx: 0, age: '', height: '', phone: '',
    goalIdx: 0, notes: '',
    // 教练选择（仅馆主）
    hasCoach: false, coachIdx: 0, coachNames: [NO_COACH], coachIds: [null],
    genders: GENDERS, goals: GOALS,
    needLogin: false, loading: true, submitting: false,
  },

  onShow() { syncTheme(this); this.init(); },

  async init() {
    const user = await getApp().ensureUser();
    if (!user) { this.setData({ loading: false, needLogin: true }); return; }
    if (user.role !== 'owner' && user.role !== 'coach') {
      fb.showError(new Error('仅工作人员可新增客户'));
      setTimeout(() => wx.navigateBack(), 900);
      return;
    }
    // 仅馆主能指定负责教练；教练新增的客户后端自动挂到自己名下
    if (user.role === 'owner') {
      try {
        const us = await api.get('/api/auth/users');
        const coaches = (us || []).filter((u) => u.role === 'coach');
        this.setData({
          hasCoach: true,
          coachNames: [NO_COACH].concat(coaches.map((c) => c.name || c.username)),
          coachIds: [null].concat(coaches.map((c) => c.id)),
        });
      } catch (e) { /* 拉不到教练列表不阻塞建档 */ }
    }
    this.setData({ loading: false });
  },

  goLogin() { wx.navigateTo({ url: '/pages/auth/auth' }); },

  onInput(e) { this.setData({ [e.currentTarget.dataset.k] : e.detail.value }); },
  onGender(e) { this.setData({ genderIdx: Number(e.detail.value) }); },
  onGoal(e) { this.setData({ goalIdx: Number(e.detail.value) }); },
  onCoach(e) { this.setData({ coachIdx: Number(e.detail.value) }); },

  async submit() {
    const name = String(this.data.name).trim();
    if (!name) { fb.showError(new Error('请填写客户姓名')); return; }
    const phone = String(this.data.phone).trim();
    if (phone && !PHONE_RE.test(phone)) { fb.showError(new Error('手机号格式不正确')); return; }

    const payload = {
      name,
      gender: GENDERS[this.data.genderIdx] === '未填写' ? '' : GENDERS[this.data.genderIdx],
      age: Number(this.data.age) || 0,
      height_cm: Number(this.data.height) || 0,
      phone,
      goal: GOALS[this.data.goalIdx] || '',
      notes: String(this.data.notes).trim(),
    };
    if (this.data.hasCoach && this.data.coachIdx > 0) {
      payload.coach_id = this.data.coachIds[this.data.coachIdx];
    }

    this.setData({ submitting: true });
    try {
      const c = await fb.withFeedback(api.post('/api/clients', payload),
        { loading: '保存中…', success: '已新增客户' });
      // 直接进新建客户的详情，方便接着录体测
      setTimeout(() => {
        wx.redirectTo({ url: `/pages/client-detail/client-detail?id=${c.id}` });
      }, 800);
    } catch (e) { /* 已提示 */ }
    this.setData({ submitting: false });
  },
});
