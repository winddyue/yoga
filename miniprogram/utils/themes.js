// 12 套界面主题（色值与 ~/workspace/your_files/ui-palettes/index.html 同源，请勿手改）
// token：bg 页面底 / card 卡片 / pri 主色 / prid 主色深 / acc 辅助色 / txt 正文 / mut 次要文字 / line 分割线
const THEMES = {
  a: { name: '山茶绿', bg: '#F5F7F2', card: '#FFFFFF', pri: '#6F8563', prid: '#4C6043', acc: '#A9BC9C', txt: '#39412F', mut: '#8A917F', line: '#E4E8DD' },
  b: { name: '雾蓝', bg: '#F2F5F9', card: '#FFFFFF', pri: '#5B7FA6', prid: '#3C5C7E', acc: '#9DB9D4', txt: '#33404F', mut: '#8B98A8', line: '#E1E8F0' },
  c: { name: '燕麦拿铁', bg: '#FAF6EF', card: '#FFFFFF', pri: '#9A7B54', prid: '#6E5638', acc: '#CBB38E', txt: '#4A4038', mut: '#A09480', line: '#ECE3D2' },
  d: { name: '墨绿鎏金', bg: '#F3F1EA', card: '#FFFFFF', pri: '#2F5249', prid: '#1E3833', acc: '#C2A15F', txt: '#2E3532', mut: '#8B8D84', line: '#E2DED2' },
  e: { name: '陶土橘', bg: '#FAF3EB', card: '#FFFFFF', pri: '#C07856', prid: '#96502F', acc: '#DDA583', txt: '#4A3A2E', mut: '#A08B76', line: '#EFE0CE' },
  f: { name: '丁香紫', bg: '#F5F3FA', card: '#FFFFFF', pri: '#8E7CC3', prid: '#66569B', acc: '#B6A8DC', txt: '#3E3A4E', mut: '#9891A8', line: '#E6E1F2' },
  g: { name: '薄荷青', bg: '#EFF6F4', card: '#FFFFFF', pri: '#4FA39B', prid: '#357771', acc: '#93C9C2', txt: '#2F3F3C', mut: '#85948F', line: '#DCEBE8' },
  h: { name: '珍珠灰×金', bg: '#F7F5F0', card: '#FFFFFF', pri: '#7D766B', prid: '#57524A', acc: '#C2A15F', txt: '#3A3733', mut: '#9A948A', line: '#E7E2D6' },
  i: { name: '珊瑚橙', bg: '#FFF4F0', card: '#FFFFFF', pri: '#F26D5B', prid: '#C74E38', acc: '#FFB3A3', txt: '#4A322B', mut: '#A08A7E', line: '#F5DDD3' },
  j: { name: '蜜糖黄', bg: '#FFFBF0', card: '#FFFFFF', pri: '#E8A020', prid: '#B87A10', acc: '#F5C86A', txt: '#4A3E28', mut: '#A09468', line: '#F0E4C8' },
  k: { name: '薄荷亮', bg: '#ECFAF8', card: '#FFFFFF', pri: '#1FA89A', prid: '#147A70', acc: '#7FD1C7', txt: '#2B3F3C', mut: '#7E9894', line: '#D2ECE9' },
  l: { name: '樱花粉', bg: '#FFF1F5', card: '#FFFFFF', pri: '#E85D8A', prid: '#BC3A64', acc: '#F5A3BE', txt: '#4A2E38', mut: '#A08894', line: '#F6DCE6' },
};
const DEFAULT_THEME = 'a';
const THEME_IDS = Object.keys(THEMES);
const STORAGE_KEY = 'theme';

function getTheme(id) { return THEMES[id] || THEMES[DEFAULT_THEME]; }
function currentThemeId() { return wx.getStorageSync(STORAGE_KEY) || DEFAULT_THEME; }

/**
 * 页面 onShow 调用：一行接入主题。
 * storage → setData({theme}) 驱动根节点 t-{{theme}} class → theme.wxss 覆写；
 * 同时同步导航栏颜色与窗口底色（主题变化时才调，避免闪烁）。
 */
function syncTheme(page) {
  const id = currentThemeId();
  const t = getTheme(id);
  if (page && page.setData) page.setData({ theme: id });
  const app = getApp();
  if (app.globalData._themeId !== id) {
    app.globalData._themeId = id;
    try {
      wx.setNavigationBarColor({ frontColor: '#ffffff', backgroundColor: t.pri });
      wx.setBackgroundColor({ backgroundColor: t.bg });
    } catch (e) {}
  }
}

module.exports = { THEMES, THEME_IDS, DEFAULT_THEME, STORAGE_KEY, getTheme, currentThemeId, syncTheme };
