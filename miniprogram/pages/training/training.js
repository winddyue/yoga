const api = require('../../api.js');
Page({
  data: { plans: [], diets: [], clientId: null },
  async onShow() {
    try {
      const c = await api.get('/api/clients/mine');
      this.setData({ clientId: c.id });
      const plans = await api.get(`/api/clients/${c.id}/plans`);
      const diets = await api.get(`/api/clients/${c.id}/diets`);
      this.setData({ plans, diets });
    } catch (e) { console.error(e); }
  },
});
