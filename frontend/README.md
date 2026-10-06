# 前端说明（React + Vite + Tailwind）

## 安装与运行

```bash
npm install
npm run dev      # http://localhost:5173，/api 已代理到本地后端
npm run build    # 生产构建，产物在 dist/
```

## 环境变量

| 变量 | 说明 | 默认 |
|------|------|------|
| VITE_API_URL | 后端 API 地址前缀 | 空（同域，靠 nginx 代理） |

构建时注入：`VITE_API_URL=https://api.example.com npm run build`。
注意这是构建时变量，docker 构建可通过 `--build-arg VITE_API_URL=…` 传入。

## 页面

- `/login` 登录
- `/` 总览（经营指标）
- `/clients` 客户列表/新增
- `/clients/:id` 客户详情（档案、健康提示、趋势曲线、评估记录）
- `/clients/:id/assess` 新增评估（手填 / 拍照上传 / 扫码录入）
- `/clients/:id/plans` 训练计划（自动生成 / 手动调整）
- `/clients/:id/diets` 饮食方案（生成 / 教练确认）
- `/users` 教练账号管理（仅馆主）
- `/fields` 自定义字段管理（仅馆主）
- `/settings` 第三方 API 设置（仅馆主）

## 扫码录入约定

二维码内容为评估字段的 JSON 字符串，例如：

```json
{"date": "2026-10-06", "weight_kg": 70, "body_fat_pct": 22.5, "waist_cm": 78}
```

扫描后自动填入表单，未知字段会被忽略。扫码使用 `html5-qrcode` 库（需 HTTPS 或 localhost 才能调用摄像头）。
