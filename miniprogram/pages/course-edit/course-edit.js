// 发布课程（馆主/教练）。后端仅支持新建（无 PUT 接口），故本页只做发布。
const api = require('../../api.js');
const { syncTheme } = require('../../utils/themes.js');
const fb = require('../../utils/feedback.js');

Page({
  data: {
    theme: 'g',
    title: '', date: '', time: '09:00', duration: 60, location: '', capacity: 20,
    coaches: [], coachIdx: 0, isOwner: false, userName: '',
    submitting: false, ready: false,
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
    const now = new Date();
    const ds = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
    this.setData({ isOwner: user.role === 'owner', userName: user.name || user.username, date: ds });
    if (user.role === 'owner') {
      try {
        const users = await api.get('/api/auth/users');
        const coaches = (users || []).filter((u) => u.role === 'coach' || u.role === 'owner');
        this.setData({ coaches, coachIdx: 0 });
      } catch (e) { /* 教练列表拉失败不阻塞提交 */ }
    } else {
      this._coachId = user.id;
    }
    this.setData({ ready: true });
  },

  onInput(e) { this.setData({ [e.currentTarget.dataset.k]: e.detail.value }); },
  onDate(e) { this.setData({ date: e.detail.value }); },
  onTime(e) { this.setData({ time: e.detail.value }); },
  onCoach(e) { this.setData({ coachIdx: Number(e.detail.value) }); },

  async submit() {
    const d = this.data;
    if (!String(d.title).trim()) { fb.showError(new Error('请填写课程标题')); return; }
    if (!d.date) { fb.showError(new Error('请选择开始日期')); return; }
    const cap = parseInt(d.capacity, 10);
    if (!cap || cap < 1) { fb.showError(new Error('容量至少为 1')); return; }
    const dur = parseInt(d.duration, 10) || 60;
    const [Y, M, D] = d.date.split('-').map(Number);
    const [h, m] = String(d.time).split(':').map(Number);
    const start = new Date(Y, M - 1, D, h || 0, m || 0);
    const end = new Date(start.getTime() + dur * 60000);
    const fmt = (x) => `${x.getFullYear()}-${String(x.getMonth() + 1).padStart(2, '0')}-${String(x.getDate()).padStart(2, '0')} ${String(x.getHours()).padStart(2, '0')}:${String(x.getMinutes()).padStart(2, '0')}`;
    const payload = {
      title: String(d.title).trim(),
      start_time: fmt(start),
      end_time: fmt(end),
      location: String(d.location || '').trim(),
      capacity: cap,
    };
    if (d.isOwner && d.coaches.length) payload.coach_id = d.coaches[d.coachIdx].id;
    else if (this._coachId) payload.coach_id = this._coachId;
    this.setData({ submitting: true });
    try {
      await fb.withFeedback(api.post('/api/courses', payload), { loading: '发布中…', success: '课程已发布' });
      setTimeout(() => wx.navigateBack(), 600);
    } catch (e) { /* withFeedback 已提示 */ }
    this.setData({ submitting: false });
  },
});
