// 用户管理（仅馆主）：列表 + 新增教练/客户账号
const api = require('../../api.js');
const { syncTheme } = require('../../utils/themes.js');
const fb = require('../../utils/feedback.js');

const ROLE_LABEL = { owner: '馆主', coach: '教练', client: '客户' };
const ROLES = [{ id: 'coach', name: '教练' }, { id: 'client', name: '客户' }];

Page({
  data: {
    theme: 'g', users: [], loading: true, loadErr: '',
    showForm: false,
    username: '', password: '', name: '',
    roles: ROLES, roleIdx: 0,
    clients: [], clientIdx: 0,
    submitting: false,
  },

  onShow() {
    syncTheme(this);
    this.init();
  },

  async init() {
    const user = await getApp().ensureUser();
    if (!user || user.role !== 'owner') {
      fb.showError(new Error('仅馆主可管理用户'));
      setTimeout(() => wx.navigateBack(), 900);
      return;
    }
    this.load();
  },

  async load() {
    this.setData({ loading: true, loadErr: '' });
    try {
      const users = await api.get('/api/auth/users');
      this.setData({ users: users || [], loading: false });
    } catch (e) {
      this.setData({ loading: false, loadErr: e.message });
    }
  },

  roleLabel(r) { return ROLE_LABEL[r] || r; },

  toggleForm() {
    if (!this.data.showForm && !this.data.clients.length) this.loadClients();
    this.setData({ showForm: !this.data.showForm });
  },

  async loadClients() {
    try {
      const list = await api.get('/api/clients');
      this.setData({ clients: list || [], clientIdx: 0 });
    } catch (e) { /* 客户列表失败则 client_id 留空 */ }
  },

  onInput(e) { this.setData({ [e.currentTarget.dataset.k]: e.detail.value }); },
  onRole(e) { this.setData({ roleIdx: Number(e.detail.value) }); },
  onClient(e) { this.setData({ clientIdx: Number(e.detail.value) }); },

  async submit() {
    const d = this.data;
    if (!String(d.username).trim()) { fb.showError(new Error('请填写用户名')); return; }
    if (!String(d.password).trim()) { fb.showError(new Error('请填写初始密码')); return; }
    const role = ROLES[d.roleIdx].id;
    const payload = {
      username: String(d.username).trim(),
      password: String(d.password),
      role,
      name: String(d.name || '').trim(),
    };
    if (role === 'client') {
      if (!d.clients.length) { fb.showError(new Error('暂无客户档案，请先建档')); return; }
      payload.client_id = d.clients[d.clientIdx].id;
    }
    this.setData({ submitting: true });
    try {
      await fb.withFeedback(api.post('/api/auth/users', payload), { loading: '创建中…', success: '账号已创建' });
      this.setData({ showForm: false, username: '', password: '', name: '', roleIdx: 0 });
      this.load();
    } catch (e) { /* withFeedback 已提示（如用户名已存在） */ }
    this.setData({ submitting: false });
  },
});
