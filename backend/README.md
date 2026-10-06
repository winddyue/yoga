# 后端说明（FastAPI）

## 安装与运行

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m app.main
# 接口文档：http://localhost:8000/docs
```

## 跑测试

```bash
python -m pytest app/tests/test_smoke.py -v
```

冒烟测试覆盖：登录 → 建客户 → 评估 → 趋势 → 自动排课 → 手动改课 → 生成饮食 → 确认饮食 → 设置页 → 越权校验。

## 接口一览

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/auth/login | 登录（表单） |
| GET | /api/auth/me | 当前用户 |
| POST/GET | /api/auth/users | 馆主管理教练账号 |
| GET/POST | /api/clients | 客户列表/新增 |
| GET/PUT/DELETE | /api/clients/{id} | 客户详情/更新/删除 |
| GET/POST | /api/custom-fields | 自定义字段 |
| POST/GET | /api/clients/{id}/assessments | 新增/查询评估 |
| GET | /api/clients/{id}/trends | 体重/体脂趋势 |
| GET | /api/clients/{id}/warnings | 健康提示 |
| POST | /api/clients/{id}/photo | 上传体测单照片 |
| POST | /api/ocr-extract | OCR 识别（预留，未配置返回 501） |
| POST | /api/clients/{id}/plans/generate | 自动生成训练计划 |
| PUT | /api/plans/{id} | 手动调整计划 |
| POST | /api/clients/{id}/diets/generate | 生成饮食方案 |
| POST | /api/diets/{id}/confirm | 教练确认饮食 |
| GET/PUT | /api/settings | 第三方 API 配置（仅馆主） |
| GET | /api/dashboard | 经营概况 |

## 切换 Postgres

设置环境变量即可，无需改代码：

```bash
DATABASE_URL=postgresql://yoga:密码@主机:5432/yoga
```

## 对接 OCR 供应商

实现 `app/services/ocr.py` 中的 `extract_assessment_from_image`：
用 `settings.OCR_API_URL` / `settings.OCR_API_KEY`（环境变量）调用供应商接口，
把识别结果映射为评估字段字典返回即可，前端无需改动。
