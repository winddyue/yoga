const api = require('../../api.js');
const { syncTheme, getTheme, currentThemeId } = require('../../utils/themes.js');
const chart = require('../../utils/chart.js');
const delta = require('../../utils/delta.js');
const fb = require('../../utils/feedback.js');

function todayYM() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
}

function todayStr() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

const CHECKIN_KIND = { training: '训练', diet: '饮食' };

Page({
  data: {
    role: '', // client | staff
    plans: [], diets: [], clientId: null,
    charts: null, metric: 'weight', empty: false,
    delta: null, deltaCls: '',
    attPct: 0, attRate: 0, monthCount: 0, daysSince: null,
    summary: null,
    pendingDiets: [], dueReassess: 0,
    // 打卡
    checkins: [], todayTraining: false, todayDiet: false,
    checkinDays: 0, recentCheckins: [],
    genPlan: false, genDiet: false,
    expandedDiet: null,
    loading: true, loadErr: '', needLogin: false,
  },
  onShow() { syncTheme(this); this.load(); },
  async load() {
    this.setData({ loading: true, loadErr: '', needLogin: false, role: '' });
    // 登录态由全局统一解析（含静默续期）
    const user = await getApp().ensureUser();
    if (!user) {
      this.setData({ loading: false, needLogin: true });
      return;
    }
    // 工作人员走训练管理视图，不再调仅客户可用的 /api/clients/mine
    if (user.role === 'coach' || user.role === 'owner') {
      await this.loadStaff();
      return;
    }
    await this.loadClient();
  },

  // 工作人员视图：待确认饮食 + 需复测提醒 + 客户管理入口
  async loadStaff() {
    try {
      const [diets, overview] = await Promise.all([
        api.get('/api/diets/pending').catch(() => []),
        api.get('/api/dashboard/coach/overview').catch(() => null),
      ]);
      this.setData({
        role: 'staff',
        pendingDiets: diets || [],
        dueReassess: (overview && overview.todos && overview.todos.due_reassess) || 0,
        loading: false,
      });
    } catch (e) {
      const expired = e.message === '未登录';
      this.setData({ loading: false, loadErr: expired ? '' : e.message, needLogin: expired });
    }
  },

  // 客户视图：健康仪表盘 + 趋势 + 计划 + 饮食
  async loadClient() {
    try {
      const c = await api.get('/api/clients/mine');
      const [plans, diets] = await Promise.all([
        api.get(`/api/clients/${c.id}/plans`),
        api.get(`/api/clients/${c.id}/diets`),
      ]);
      let charts = null;
      try { charts = await api.get('/api/dashboard/me/charts'); } catch (e) {}
      // 本月总结：失败静默不显示
      let summary = null;
      try { summary = await api.get('/api/dashboard/me/monthly'); } catch (e) {}
      const hasTrend = !!(charts && charts.trends && charts.trends.dates.length);
      // 健康仪表盘数据：出勤率 / 本月体测次数 / 距上次评估天数
      const attRate = c.attendance_rate || 0;
      const dates = (charts && charts.trends && charts.trends.dates) || [];
      const ym = todayYM();
      const monthCount = dates.filter((d) => String(d).slice(0, 7) === ym).length;
      let daysSince = null;
      if (dates.length) {
        const last = new Date(String(dates[dates.length - 1]) + 'T00:00:00');
        const now = new Date();
        now.setHours(0, 0, 0, 0);
        daysSince = Math.max(0, Math.round((now - last) / 86400000));
      }
      this.setData({
        role: 'client',
        clientId: c.id,
        plans: plans || [], diets: diets || [], charts,
        attRate, attPct: Math.round(attRate * 100),
        monthCount, daysSince, summary,
        empty: !(plans || []).length && !(diets || []).length && !hasTrend,
        loading: false,
      }, () => {
        this.computeDelta();
        this.loadCheckins();
        setTimeout(() => { this.drawTrend(); this.drawDash(); }, 80);
      });
    } catch (e) {
      if (e.message === '未登录') {
        this.setData({ loading: false, needLogin: true });
        return;
      }
      this.setData({ loading: false, loadErr: e.message });
    }
  },
  goLogin() { wx.navigateTo({ url: '/pages/auth/auth' }); },
  goMeasure() { wx.navigateTo({ url: '/pages/measure/measure' }); },
  goClients() { wx.navigateTo({ url: '/pages/clients/clients' }); },

  // 计划获取：AI 生成训练计划（客户可给自己调用）
  async aiGeneratePlan() {
    if (this.data.genPlan || !this.data.clientId) return;
    this.setData({ genPlan: true });
    try {
      await fb.withFeedback(
        api.post(`/api/clients/${this.data.clientId}/plans/generate`, {}),
        { loading: 'AI 生成中…' },
      );
      fb.showSuccess('训练计划已生成');
      this.loadClient();
    } catch (e) { /* 已提示 */ }
    this.setData({ genPlan: false });
  },

  // 计划获取：AI 生成饮食方案（客户可给自己调用）
  async aiGenerateDiet() {
    if (this.data.genDiet || !this.data.clientId) return;
    this.setData({ genDiet: true });
    try {
      await fb.withFeedback(
        api.post(`/api/clients/${this.data.clientId}/diets/ai-generate`, {}),
        { loading: 'AI 生成中…' },
      );
      fb.showSuccess('饮食方案已生成');
      this.loadClient();
    } catch (e) {
      if (/503|未配置/.test(e.message || '')) fb.showError(new Error('馆主尚未配置 AI 服务，请联系馆主'));
    }
    this.setData({ genDiet: false });
  },

  // 计划获取：请求教练制定
  async requestPlan(e) {
    const kind = e.currentTarget.dataset.kind; // training | diet
    try {
      await fb.withFeedback(
        api.post('/api/plan-requests', { kind }),
        { loading: '发送中…' },
      );
      fb.showSuccess('已通知教练');
    } catch (e) { /* 400 无教练时后端返回友好提示，已显示 */ }
  },

  // 打卡：本月记录（失败静默）
  async loadCheckins() {
    try {
      const list = await api.get(`/api/checkins/mine?ym=${todayYM()}`);
      const arr = list || [];
      const today = todayStr();
      const recent = arr.slice().sort((a, b) => String(b.date).localeCompare(String(a.date))).slice(0, 5)
        .map((c) => ({ ...c, kindText: CHECKIN_KIND[c.kind] || c.kind }));
      this.setData({
        checkins: arr,
        todayTraining: arr.some((c) => c.date === today && c.kind === 'training'),
        todayDiet: arr.some((c) => c.date === today && c.kind === 'diet'),
        checkinDays: new Set(arr.map((c) => c.date)).size,
        recentCheckins: recent,
      });
    } catch (e) { /* 后端未就绪时静默 */ }
  },

  // 打卡：选直接打卡 / 拍照打卡
  async checkin(e) {
    const kind = e.currentTarget.dataset.kind;
    let r;
    try {
      r = await wx.showActionSheet({ itemList: ['直接打卡', '拍照打卡'] });
    } catch (err) { return; } // 用户取消
    if (r.tapIndex === 1) {
      this.photoCheckin(kind);
    } else {
      this.doCheckin(kind, '');
    }
  },

  // 打卡：拍照上传后再打卡（写法参考 intake 页）
  photoCheckin(kind) {
    wx.chooseMedia({ count: 1, mediaType: ['image'], sourceType: ['album', 'camera'] })
      .then((res) => {
        if (!res || !res.tempFiles || !res.tempFiles.length) return;
        const filePath = res.tempFiles[0].tempFilePath;
        const token = wx.getStorageSync('token') || '';
        fb.showLoading('上传中…');
        wx.uploadFile({
          url: api.BASE + '/api/uploads',
          filePath,
          name: 'file',
          header: { Authorization: token ? `Bearer ${token}` : '' },
          success: (up) => {
            let data = null;
            try { data = JSON.parse(up.data); } catch (err) {}
            if (up.statusCode >= 400 || !data || !data.path) {
              fb.showError(new Error((data && data.detail) || '上传失败，请重试'));
              return;
            }
            this.doCheckin(kind, data.path);
          },
          fail: () => fb.showError(new Error('网络连接失败，请检查网络')),
          complete: () => fb.hideLoading(),
        });
      })
      .catch(() => { /* 用户取消 */ });
  },

  // 打卡提交
  async doCheckin(kind, photoPath) {
    try {
      const body = { kind };
      if (photoPath) body.photo_path = photoPath;
      await fb.withFeedback(api.post('/api/checkins', body), { loading: '打卡中…' });
      fb.showSuccess('打卡成功');
      this.loadCheckins();
    } catch (e) {
      // 重复打卡 400 等，后端返回友好提示，已显示
      this.loadCheckins(); // 刷新已打卡态
    }
  },

  // 计划详情 / 饮食展开
  goPlanDetail(e) {
    wx.navigateTo({ url: `/pages/plan-detail/plan-detail?id=${e.currentTarget.dataset.id}` });
  },
  toggleDiet(e) {
    const id = e.currentTarget.dataset.id;
    this.setData({ expandedDiet: this.data.expandedDiet === id ? null : id });
  },

  // 打卡照片点开放大（鉴权下载：header 带 token，拿到临时文件再预览）
  previewPhoto(e) {
    const path = e.currentTarget.dataset.path;
    if (!path) return;
    const token = wx.getStorageSync('token') || '';
    wx.downloadFile({
      url: api.BASE + path,
      header: token ? { Authorization: `Bearer ${token}` } : {},
      success(res) {
        if (res.statusCode === 200) wx.previewImage({ urls: [res.tempFilePath] });
        else fb.toast('图片加载失败');
      },
      fail() { fb.toast('图片加载失败'); },
    });
  },

  // 工作人员：一键确认饮食（逻辑同教练工作台）
  async confirmDiet(e) {
    const id = e.currentTarget.dataset.id;
    const ok = await fb.confirm('确认该饮食方案？确认后将通知客户。', '确认');
    if (!ok) return;
    try {
      await fb.withFeedback(api.post(`/api/diets/${id}/confirm`, {}), { loading: '确认中…' });
      fb.showSuccess('已确认');
      this.loadStaff();
    } catch (err) { /* 已提示 */ }
  },

  // 趋势指标切换：体重 / 体脂 / 腰围
  switchMetric(e) {
    const m = e.currentTarget.dataset.m;
    if (m === this.data.metric) return;
    this.setData({ metric: m }, () => { this.computeDelta(); this.drawTrend(); });
  },

  // 较上次对比 chip（当前 tab 指标）
  computeDelta() {
    const t = this.data.charts && this.data.charts.trends;
    const d = delta.lastDelta(t, this.data.metric);
    this.setData({ delta: d, deltaCls: delta.deltaCls(d) });
  },

  drawTrend() {
    const charts = this.data.charts;
    if (!charts || !charts.trends || !charts.trends.dates.length) return;
    const th = getTheme(currentThemeId());
    const m = this.data.metric;
    const color = m === 'weight' ? th.pri : (m === 'body_fat' ? '#D9A85F' : th.acc);
    chart.drawTrend(this, 'trainTrend', charts.trends, m, color);
  },

  // 健康仪表盘：出勤率圆环
  drawDash() {
    chart.drawRing(this, 'trainRing', this.data.attRate || 0);
  },
});
