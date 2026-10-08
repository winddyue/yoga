const { syncTheme } = require('../../utils/themes.js');
// 关于我们：馆名与联系方式为占位内容，上线前请替换为实际信息（TODO）
const GYM = {
  name: '本瑜伽馆',
  desc: '我们提供瑜伽课程预约、到店签到、训练计划与饮食方案查看、体测评估记录等会员服务，帮助你更稳定地坚持练习。',
  phone: '',   // TODO：替换为前台电话，留空则不展示该行
  address: '', // TODO：替换为门店地址
  hours: '',   // TODO：替换为营业时间
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
