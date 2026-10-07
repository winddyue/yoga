const api = require('../../api.js');
const fb = require('../../utils/feedback.js');

// 预约状态 -> 展示文案
const STATUS_TEXT = {
  booked: '已预约',
  waitlist: '候补中',
  checked_in: '已签到',
  no_show: '爽约',
  cancelled: '已取消',
};

Page({
  data: { courses: [], loading: true, loadErr: '', needLogin: false },

  onShow() { this.load(); },

  async load() {
    this.setData({ loading: true, loadErr: '', needLogin: false });
    try {
      const [courses, mine] = await Promise.all([
        api.get('/api/courses'),
        api.get('/api/bookings/mine').catch((e) => {
          // 未登录时"我的预约"取不到是正常的，不当作错误
          if (e.message === '未登录') return null;
          throw e;
        }),
      ]);
      // 我的预约按课程建索引：course_id -> {status, text}
      const mineMap = {};
      (mine || []).forEach((b) => { mineMap[b.course_id] = b; });
      const list = (courses || []).map((c) => {
        const b = mineMap[c.id];
        return {
          ...c,
          my_status: b ? b.status : '',
          my_status_text: b ? (STATUS_TEXT[b.status] || b.status) : '',
          full: c.booked_count >= c.capacity,
        };
      });
      this.setData({ courses: list, loading: false, needLogin: mine === null });
    } catch (e) {
      if (e.message === '未登录') {
        this.setData({ loading: false, needLogin: true });
        return;
      }
      this.setData({ loading: false, loadErr: e.message });
    }
  },

  goLogin() { wx.navigateTo({ url: '/pages/auth/auth' }); },

  // 预约：满员自动候补，后端重复预约会 400
  async book(e) {
    if (this.data.needLogin) return this.goLogin();
    const id = e.currentTarget.dataset.id;
    try {
      const r = await fb.withFeedback(
        api.post(`/api/courses/${id}/book`, {}),
        { loading: '预约中…' },
      );
      fb.showSuccess(r.status === 'waitlist' ? '已进入候补' : '预约成功');
      this.load();
    } catch (e) { /* 错误提示已由 withFeedback 弹出 */ }
  },

  async cancel(e) {
    if (this.data.needLogin) return this.goLogin();
    const id = e.currentTarget.dataset.id;
    if (!await fb.confirm('确定取消该预约吗？候补将自动递补。', '取消预约')) return;
    try {
      await fb.withFeedback(api.post(`/api/courses/${id}/cancel`, {}), { loading: '取消中…' });
      this.load();
    } catch (e) { /* 已提示 */ }
  },

  // 扫码签到：扫教练出示的签到二维码（内容为签到码）。
  // 后端校验码值 + 签到时间窗（开课前30分钟~开课后60分钟），失败原因直接提示
  async scanCheckin() {
    if (this.data.needLogin) return this.goLogin();
    let scan;
    try {
      scan = await new Promise((resolve, reject) => {
        wx.scanCode({
          success: resolve,
          fail: () => reject(new Error('已取消扫码')),
        });
      });
    } catch (e) {
      return; // 用户取消扫码，无需提示
    }
    // 二维码内容约定为 "yoga:checkin:课程id:签到码"（教练端生成）
    const parts = String(scan.result || '').split(':');
    if (!(parts[0] === 'yoga' && parts[1] === 'checkin' && parts.length === 4)) {
      fb.showError(null, '二维码格式不正确，请扫教练出示的签到码');
      return;
    }
    const courseId = parts[2];
    const code = parts[3];
    try {
      await fb.withFeedback(
        api.post(`/api/courses/${courseId}/checkin`, { code }),
        { loading: '签到中…' },
      );
      fb.showSuccess('签到成功');
      this.load();
    } catch (e) { /* 时间窗/码值错误已由 withFeedback 提示 */ }
  },
});
