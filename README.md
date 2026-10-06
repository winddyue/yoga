# 瑜伽馆 / 健身房客户管理

给瑜伽馆、健身房馆主和教练用的极简客户管理应用：管客户身体档案、自动排训练计划、管每天的饮食方案。

设计参考了开源项目 wger（训练编排）、SparkyFitness（身体指标追踪）、Fud AI（热量与营养素公式）的思路，只保留最简核心。

## 技术栈

- 后端：Python FastAPI + SQLAlchemy，默认 SQLite（零配置），可通过 `DATABASE_URL` 切换 Postgres
- 前端：React 18 + Vite + Tailwind CSS + react-router-dom
- 部署：docker-compose 一键部署（2核4G 轻量云服务器足够）

## 目录结构

```
yoga-app/
├── docker-compose.yml      # 一键部署
├── .env.example            # 环境变量模板（复制为 .env 后修改）
├── backend/                # 后端
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py         # 入口：路由挂载、建表、默认账号
│       ├── config.py       # 环境变量配置
│       ├── models.py       # 数据模型
│       ├── schemas.py      # 接口数据校验
│       ├── auth.py         # JWT 登录与角色守卫
│       ├── routers/        # 各业务接口
│       ├── services/       # 营养计算 / 训练计划生成 / OCR 预留
│       └── tests/          # 冒烟测试
└── frontend/               # 前端
    ├── Dockerfile / nginx.conf
    └── src/
        ├── pages/          # 登录、总览、客户、评估、计划、饮食、设置等
        └── components/     # 布局、趋势图、扫码、上传
```

## 快速启动（本地开发）

后端：

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m app.main          # http://localhost:8000
```

前端：

```bash
cd frontend
npm install
npm run dev                 # http://localhost:5173（已代理 /api 到后端）
```

默认馆主账号：`admin / admin123`（首次启动自动创建，请尽快修改）。

## 一键部署（云服务器）

```bash
cp .env.example .env   # 按需修改 SECRET_KEY、ADMIN_PASSWORD 等
docker compose up -d --build
# 浏览器打开 http://服务器IP 即可使用
```

数据（SQLite 文件与上传照片）保存在 docker volume `yoga-data` 中，容器重建不丢失。

## 功能概览

1. **客户档案**：基本信息、身体成分、围度、健康指标、训练目标；馆主可自定义字段增减；多次评估记录，体重/体脂趋势曲线
2. **训练排课**：按目标自动生成一周计划，教练可手动增删动作、改时间
3. **饮食方案**：按 Mifflin-St Jeor / Katch-McArdle 公式算热量与三大营养素，精确到三餐加餐；需教练确认
4. **角色**：馆主看全馆概况、管教练账号与自定义字段；教练只看自己客户
5. **评估录入**：支持拍照上传（OCR 接口预留）、扫码自动填表
6. **设置页**：配置第三方 API 地址；密钥只存服务器环境变量，前端看不到明文

## 安全注意

- 任何密钥（API Key、SECRET_KEY）只通过环境变量 / `.env` 配置，绝不写进代码、不提交到仓库
- 生产环境务必修改 `SECRET_KEY` 和默认管理员密码
- 健康提示仅为展示参考，不构成医疗建议
