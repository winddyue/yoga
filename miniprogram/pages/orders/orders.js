// 我的订单：订单列表（状态中文 + 金额 + 时间）
const api = require('../../api.js');
const { syncTheme } = require('../../utils/themes.js');
const fb = require('../../utils/feedback.js');
const { fmtYuan } = require('../../utils/money.js');

const STATUS_TEXT = {
  pending: '待支付',
  paid: '已支付',
  refunded: '已退款',
  closed: '已关闭',
};

Page({
  data: { orders: [], loading: true },

  onShow() { syncTheme(this); this.load(); },

  async load() {
    this.setData({ loading: true });
    const user = await getApp().ensureUser();
    if (!user) { this.setData({ loading: false }); return; }
    try {
      const list = await api.get('/api/orders/mine');
      this.setData({
        orders: (list || []).map((o) => ({
          ...o,
          amountText: fmtYuan(o.amount_cents),
          statusText: STATUS_TEXT[o.status] || o.status,
          statusCls: o.status === 'paid' ? 'st-paid' : (o.status === 'pending' ? 'st-pending' : 'st-other'),
        })),
        loading: false,
      });
    } catch (e) {
      fb.showError(e, '订单加载失败');
      this.setData({ loading: false });
    }
  },
});
