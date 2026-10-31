// 团购商城：商品列表 → 下单 → 微信支付
const api = require('../../api.js');
const { syncTheme } = require('../../utils/themes.js');
const fb = require('../../utils/feedback.js');
const { fmtYuan } = require('../../utils/money.js');

Page({
  data: { products: [], loading: true, paying: false },

  onShow() { syncTheme(this); this.load(); },

  async load() {
    this.setData({ loading: true });
    try {
      const list = await api.get('/api/products');
      this.setData({
        products: (list || []).map((p) => ({ ...p, priceText: fmtYuan(p.price_cents) })),
        loading: false,
      });
    } catch (e) {
      fb.showError(e, '商品加载失败');
      this.setData({ loading: false });
    }
  },

  async buy(e) {
    if (this.data.paying) return;
    const pid = e.currentTarget.dataset.id;
    const user = await getApp().ensureUser();
    if (!user) { wx.navigateTo({ url: '/pages/auth/auth' }); return; }
    this.setData({ paying: true });
    try {
      const order = await fb.withFeedback(
        api.post('/api/orders', { product_id: pid }),
        { loading: '下单中…' }
      );
      await this.requestPay(order.prepay_params);
      fb.showSuccess('支付成功');
      wx.navigateTo({ url: '/pages/orders/orders' });
    } catch (err) {
      if (err && err.message === '__cancel__') {
        wx.showToast({ title: '已取消支付', icon: 'none', duration: 1500 });
      } else {
        // 503 未配置微信支付时后端返回友好文案，直接透出
        fb.showError(err, '下单失败，请重试');
      }
    } finally {
      this.setData({ paying: false });
    }
  },

  // 调起微信支付；用户主动取消单独标记，不走报错通道
  requestPay(params) {
    return new Promise((resolve, reject) => {
      wx.requestPayment({
        timeStamp: params.timeStamp,
        nonceStr: params.nonceStr,
        package: params.package,
        signType: params.signType,
        paySign: params.paySign,
        success: () => resolve(),
        fail: (res) => {
          const msg = (res && res.errMsg) || '';
          if (msg.indexOf('cancel') >= 0) reject(new Error('__cancel__'));
          else reject(new Error('支付失败，请重试'));
        },
      });
    });
  },
});
