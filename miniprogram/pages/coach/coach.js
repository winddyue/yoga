const api = require('../../api.js');
const fb = require('../../utils/feedback.js');

Page({
  data: { courses: [], roster: [], cur: null, qr: null, qrTitle: '' },

  onShow() { this.load(); },

  async load() {
    try {
      const courses = await api.get('/api/courses');
      this.setData({ courses: courses || [] });
    } catch (e) {
      fb.showError(e, '课程加载失败');
    }
  },

  // 出示签到二维码：客户用约课页"扫码签到"扫描
  async showQr(e) {
    const id = e.currentTarget.dataset.id;
    try {
      const r = await fb.withFeedback(
        api.get(`/api/courses/${id}/qrcode`),
        { loading: '生成二维码…' },
      );
      const course = this.data.courses.find((c) => c.id === Number(id));
      this.setData({ qr: `data:image/png;base64,${r.png_base64}`,
                     qrTitle: (course && course.title) || '签到' });
    } catch (e) { /* 已提示 */ }
  },

  hideQr() { this.setData({ qr: null }); },

  async openRoster(e) {
    const id = e.currentTarget.dataset.id;
    try {
      const roster = await api.get(`/api/courses/${id}/roster`);
      this.setData({ roster: roster || [], cur: id });
    } catch (e) {
      fb.showError(e, '名单加载失败');
    }
  },

  // 手动确认签到（补签，不受时间窗限制）
  async checkin(e) {
    const cid = e.currentTarget.dataset.cid;
    try {
      await fb.withFeedback(
        api.post(`/api/courses/${this.data.cur}/checkin`, { client_id: cid }),
        { loading: '签到中…', success: '已签到' },
      );
      this.openRoster({ currentTarget: { dataset: { id: this.data.cur } } });
    } catch (e) { /* 已提示 */ }
  },
});
