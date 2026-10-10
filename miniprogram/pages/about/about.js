const { syncTheme } = require('../../utils/themes.js');
// 关于我们：门店信息。改这里即可，页面会自动展示/隐藏对应行。
// phone 留空时不展示「前台电话」一行。
const GYM = {
  name: '瑜美瑜伽',
  desc: '我们提供瑜伽课程预约、到店签到、训练计划与饮食方案查看、体测评估记录等会员服务，帮助你更稳定地坚持练习。',
  phone: '',   // 留空则不展示该行；有前台电话时填在这里
  address: '柳南区航鹰大道魅力首座1-201号',
  hours: '8:00-21:00',
};

Page({
  onShow() { syncTheme(this); },
  data: {
    gym: GYM,
    version: '1.0.0',
    updated: '2026-10-07',
  },

  call() {
    if (!GYM.phone) return;
    wx.makePhoneCall({ phoneNumber: GYM.phone });
  },

  openAgreement(e) {
    const t = e.currentTarget.dataset.t;
    wx.navigateTo({ url: `/pages/agreement/agreement?tab=${t}` });
  },
});
