// 界面风格：12 套配色宫格选择，即时生效
const { THEMES, THEME_IDS, getTheme, currentThemeId, STORAGE_KEY } = require('../../utils/themes.js');

Page({
  data: { themes: [], current: 'g', theme: 'g' },

  onShow() {
    const cur = currentThemeId();
    this.setData({
      themes: THEME_IDS.map((id) => ({ id, name: THEMES[id].name, pri: THEMES[id].pri, bg: THEMES[id].bg })),
      current: cur,
      theme: cur,
    });
    // 同步导航栏（与 syncTheme 一致，保证本页导航栏也跟随）
    const t = getTheme(cur);
    try { wx.setNavigationBarColor({ frontColor: '#ffffff', backgroundColor: t.pri }); } catch (e) {}
  },

  pick(e) {
    const id = e.currentTarget.dataset.id;
    if (!THEMES[id]) return;
    wx.setStorageSync(STORAGE_KEY, id);
    const t = getTheme(id);
    try {
      wx.setNavigationBarColor({ frontColor: '#ffffff', backgroundColor: t.pri });
      wx.setBackgroundColor({ backgroundColor: t.bg });
    } catch (err) {}
    getApp().globalData._themeId = id;
    this.setData({ current: id, theme: id });
    wx.showToast({ title: '已切换为' + t.name, icon: 'none' });
  },
});
