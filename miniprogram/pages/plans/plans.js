// 训练计划管理（工作人员）：列表 + AI 生成 + 编辑（全量覆盖 days）。
const api = require('../../api.js');
const { syncTheme } = require('../../utils/themes.js');
const fb = require('../../utils/feedback.js');

// 把某天的 exercises 转成可编辑文本行："深蹲 3x12"
function exercisesToText(exs) {
  return (exs || []).map((e) => `${e.name || ''} ${e.sets || 3}x${e.reps || '12'}`.trim()).join('\n');
}

// 解析文本行回 exercises：行格式 "动作名 组数x次数"，组数缺省 3，次数缺省 12
function textToExercises(text) {
  return String(text || '').split('\n')
    .map((l) => l.trim()).filter(Boolean)
    .map((l) => {
      const m = l.match(/^(.*?)\s+(\d+)\s*[x×*]\s*(.+)$/);
      if (m) return { name: m[1].trim(), sets: parseInt(m[2], 10) || 3, reps: String(m[3]).trim() };
      return { name: l, sets: 3, reps: '12' };
    })
    .filter((e) => e.name);
}

Page({
  data: {
    theme: '', clientId: null, clientName: '',
    plans: [], loading: true, loadErr: '', needLogin: false,
    editingId: null, editWeek: '', editDays: [], saving: false, generating: false,
  },

  onLoad(options) {
    this.setData({ clientId: options.clientId ? Number(options.clientId) : null });
  },

  onShow() { syncTheme(this); this.load(); },

  async load() {
    this.setData({ loading: true, loadErr: '', needLogin: false });
    const user = await getApp().ensureUser();
    if (!user) {
      this.setData({ loading: false, needLogin: true });
      return;
    }
    if (user.role !== 'coach' && user.role !== 'owner') {
      fb.showError({ message: '无权限，仅工作人员可管理' });
      setTimeout(() => wx.navigateBack(), 900);
      return;
    }
    if (!this.data.clientId) {
      this.setData({ loading: false, loadErr: '缺少客户 id' });
      return;
    }
    try {
      const [client, plans] = await fb.withFeedback(Promise.all([
        api.get(`/api/clients/${this.data.clientId}`),
        api.get(`/api/clients/${this.data.clientId}/plans`),
      ]), { loading: '加载中…' });
      const rows = (plans || []).map((p) => ({
        id: p.id, week_start: p.week_start, status: p.status,
        days: (p.days || []).map((d) => ({
          day: d.day, time: d.time || '',
          exText: (d.exercises || []).map((e) => e.name).filter(Boolean).join('、') || '—',
        })),
      }));
      this.setData({ clientName: client.name || '', plans: rows, loading: false, editingId: null });
    } catch (e) {
      const expired = e.message === '未登录';
      this.setData({ loading: false, loadErr: expired ? '' : e.message, needLogin: expired });
    }
  },

  goLogin() { wx.navigateTo({ url: '/pages/auth/auth' }); },

  // AI 生成一周计划（旧计划自动归档）
  async generate() {
    if (this.data.generating) return;
    const ok = await fb.confirm('将自动生成一周训练计划，当前生效计划会被归档。继续？', 'AI 生成计划');
    if (!ok) return;
    this.setData({ generating: true });
    try {
      await fb.withFeedback(
        api.post(`/api/clients/${this.data.clientId}/plans/generate`),
        { loading: '生成中…', success: '已生成' },
      );
      this.load();
    } catch (e) {
      fb.showError(e, '生成失败');
    } finally {
      this.setData({ generating: false });
    }
  },

  // 进入编辑态：把 days 展开为可编辑文本
  startEdit(e) {
    const id = e.currentTarget.dataset.id;
    const p = this.data.plans.find((x) => x.id === id);
    if (!p) return;
    this.setData({
      editingId: id,
      editWeek: p.week_start || '',
      editDays: p.days.map((d) => ({
        day: d.day, time: d.time || '',
        text: '', // 用原 exercises 重建文本需原数据，这里先从后端取全量
      })),
    });
    this._loadFullPlan(id);
  },

  async _loadFullPlan(id) {
    try {
      const plans = await api.get(`/api/clients/${this.data.clientId}/plans`);
      const p = (plans || []).find((x) => x.id === id);
      if (!p) return;
      this.setData({
        editDays: (p.days || []).map((d) => ({
          day: d.day, time: d.time || '', text: exercisesToText(d.exercises),
        })),
      });
    } catch (e) { fb.showError(e, '加载计划详情失败'); }
  },

  cancelEdit() { this.setData({ editingId: null, editDays: [] }); },

  onWeekInput(e) { this.setData({ editWeek: e.detail.value }); },
  onDayTimeInput(e) {
    const i = e.currentTarget.dataset.i;
    const days = this.data.editDays.slice();
    days[i].time = e.detail.value;
    this.setData({ editDays: days });
  },
  onDayTextInput(e) {
    const i = e.currentTarget.dataset.i;
    const days = this.data.editDays.slice();
    days[i].text = e.detail.value;
    this.setData({ editDays: days });
  },

  async saveEdit() {
    if (this.data.saving || !this.data.editingId) return;
    const days = this.data.editDays.map((d) => ({
      day: d.day, time: d.time || '', exercises: textToExercises(d.text),
    }));
    this.setData({ saving: true });
    try {
      await fb.withFeedback(
        api.put(`/api/plans/${this.data.editingId}`, { week_start: this.data.editWeek, days }),
        { loading: '保存中…', success: '已保存' },
      );
      this.load();
    } catch (e) {
      fb.showError(e, '保存失败');
    } finally {
      this.setData({ saving: false });
    }
  },
});
