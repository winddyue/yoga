// 打卡共享逻辑：直接打卡 / 拍照打卡 / 交互选择。
// 客户给自己打卡；工作人员带 clientId 可代打卡（后端 /api/checkins?client_id=）。
// 抽出来的原因：训练页与首页金刚区都要用，避免两处各写一份上传+提交。
const api = require('../api.js');
const fb = require('./feedback.js');

const KINDS = { training: '训练', diet: '饮食' };

// 上传照片 → resolve 服务端返回的相对路径（如 /api/files/xxx.jpg）
function uploadPhoto(filePath) {
  return new Promise((resolve, reject) => {
    const token = wx.getStorageSync('token') || '';
    wx.uploadFile({
      url: api.BASE + '/api/uploads',
      filePath,
      name: 'file',
      header: { Authorization: token ? `Bearer ${token}` : '' },
      success: (up) => {
        let data = null;
        try { data = JSON.parse(up.data); } catch (e) { /* 非 JSON 视为失败 */ }
        if (up.statusCode >= 400 || !data || !data.path) {
          reject(new Error((data && data.detail) || '上传失败，请重试'));
          return;
        }
        resolve(data.path);
      },
      fail: () => reject(new Error('网络连接失败，请检查网络')),
    });
  });
}

// 提交打卡（clientId 仅在工作人员代打卡时传）
function submit(kind, photoPath, clientId) {
  const body = { kind };
  if (photoPath) body.photo_path = photoPath;
  const url = clientId ? `/api/checkins?client_id=${clientId}` : '/api/checkins';
  return api.post(url, body);
}

// 直接打卡（不附照片）
async function direct(kind, clientId) {
  try {
    await fb.withFeedback(submit(kind, '', clientId), { loading: '打卡中…' });
    fb.showSuccess('打卡成功');
    return true;
  } catch (e) {
    // 重复打卡（今日已打卡）等由后端给出友好提示，这里不重复弹
    return false;
  }
}

// 拍照打卡：选图 → 上传 → 打卡
async function photo(kind, clientId) {
  let r;
  try {
    r = await wx.chooseMedia({ count: 1, mediaType: ['image'], sourceType: ['album', 'camera'] });
  } catch (e) {
    return false; // 用户取消
  }
  if (!r || !r.tempFiles || !r.tempFiles.length) return false;
  fb.showLoading('上传中…');
  try {
    const path = await uploadPhoto(r.tempFiles[0].tempFilePath);
    fb.hideLoading();
    await fb.withFeedback(submit(kind, path, clientId), { loading: '打卡中…' });
    fb.showSuccess('打卡成功');
    return true;
  } catch (e) {
    fb.hideLoading();
    fb.showError(e, '打卡失败');
    return false;
  }
}

// 交互入口：弹「直接打卡 / 拍照打卡」让用户选
async function interactive(kind, clientId) {
  let r;
  try {
    r = await wx.showActionSheet({ itemList: ['直接打卡', '拍照打卡'] });
  } catch (e) {
    return false; // 用户取消
  }
  return r.tapIndex === 1 ? photo(kind, clientId) : direct(kind, clientId);
}

module.exports = { KINDS, direct, photo, interactive };
