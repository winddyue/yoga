// 教练工作台：待办驱动。
// 此前这里把「全量课程列表」当主体，而 /api/courses 既不按教练过滤也不按时间过滤，
// 把历史课与测试课全列了出来；课程预约功能暂隐后，这里只保留教练真正要处理的事。
const api = require('../../api.js');
const { syncTheme } = require('../../utils/themes.js');
const fb = require('../../utils/feedback.js');

Page({
  data: {
    theme: '',
    pendingDiets: [], dueReassess: 0, clients: [],
    loading: true, needLogin: false, loadErr: '',
  },

  onShow() { syncTheme(this); this.load(); },

  async load() {
    this.setData({ loading: true, loadErr: '', needLogin: false });
    const user = await getApp().ensureUser();
    if (!user) { this.setData({ loading: false, needLogin: true }); return; }
    if (user.role !== 'owner' && user.role !== 'coach') {
      fb.showError(new Error('仅工作人员可访问'));
      setTimeout(() => wx.navigateBack(), 900);
      return;
    }
    try {
      // coach/overview：馆主看全馆、教练看名下；含状态灯与待办计数
      const d = await api.get('/api/dashboard/coach/overview');
      const clients = (d.clients || []).map((c) => ({
        id: c.id,
        name: c.name,
        goal: c.goal || '',
        att: Math.round((c.attendance_rate || 0) * 100),
        status: c.status || '',
        action: c.action || '',
      }));
      this.setData({
        clients,
        dueReassess: (d.todos && d.todos.due_reassess) || 0,
        loading: false,
      });
    } catch (e) {
      this.setData({ loading: false, loadErr: e.message });
    }
    try {
      const diets = await api.get('/api/diets/pending');
      this.setData({ pendingDiets: diets || [] });
    } catch (e) { /* 非馆主/教练不可见时忽略 */ }
  },

  goLogin() { wx.navigateTo({ url: '/pages/auth/auth' }); },

  goIntake() { wx.navigateTo({ url: '/pages/intake/intake' }); },
  goNewClient() { wx.navigateTo({ url: '/pages/client-form/client-form' }); },
  goClients() { wx.navigateTo({ url: '/pages/clients/clients' }); },
  goClientDetail(e) {
    const id = e.currentTarget.dataset.id;
    if (id) wx.navigateTo({ url: `/pages/client-detail/client-detail?id=${id}` });
  },

  // 待确认饮食：一键确认
  async confirmDiet(e) {
    const id = e.currentTarget.dataset.id;
    const ok = await fb.confirm('确认该饮食方案？确认后将通知客户。', '确认');
    if (!ok) return;
    try {
      await fb.withFeedback(api.post(`/api/diets/${id}/confirm`, {}), { loading: '确认中…' });
      fb.showSuccess('已确认');
      this.load();
    } catch (err) { /* 已提示 */ }
  },
});
