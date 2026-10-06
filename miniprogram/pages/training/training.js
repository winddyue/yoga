const api = require('../../api.js');
const fb = require('../../utils/feedback.js');

Page({
  data: { plans: [], diets: [], clientId: null, loading: true, loadErr: '' },
  onShow() { this.load(); },
  async load() {
    this.setData({ loading: true, loadErr: '' });
    try {
      const c = await api.get('/api/clients/mine');
      this.setData({ clientId: c.id });
      const [plans, diets] = await Promise.all([
        api.get(`/api/clients/${c.id}/plans`),
        api.get(`/api/clients/${c.id}/diets`),
      ]);
      this.setData({ plans: plans || [], diets: diets || [], loading: false });
    } catch (e) {
      this.setData({ loading: false, loadErr: e.message });
    }
  },
});
