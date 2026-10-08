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

## 数据库迁移（Alembic）

表结构变更走 Alembic 迁移，不直接改库。配置在 `backend/alembic.ini`，
迁移脚本在 `backend/alembic/versions/`，连接串复用 `DATABASE_URL`
环境变量（默认 SQLite）。

```bash
cd backend
alembic upgrade head                          # 升级到最新（部署时执行）
alembic revision --autogenerate -m "加字段xxx"  # 改完 models.py 后生成迁移
alembic downgrade -1                          # 回滚一个版本（应急）
```

注意事项：
- 生成迁移后**人工检查一遍** autogenerate 的内容再提交（它检测不到
  数据迁移、部分索引的 WHERE 条件变化等，需要手补）。
- SQLite 下已默认开启 batch 模式（`render_as_batch=True`），
  `ALTER TABLE` 受限操作会自动用"建新表→导数据→删旧表"模拟。
- 现有迁移 `0001_booking_seats` 是幂等的：检测到列/索引已存在会自动跳过。
  新库由 app 启动时的 `create_all` 建出完整表结构；老库（create_all 建表、
  后续 models 加列）执行 `alembic upgrade head` 补齐。
  迁移幂等，所以老库直接 `upgrade head` 即可，不需要 `stamp`——
  `stamp head` 会跳过执行，导致缺列的老库永远补不上列。
- 迁移里不要写业务逻辑，只做 schema 变更 + 必要的回填。

## 对接 OCR 供应商

实现 `app/services/ocr.py` 中的 `extract_assessment_from_image`：
用 `settings.OCR_API_URL` / `settings.OCR_API_KEY`（环境变量）调用供应商接口，
把识别结果映射为评估字段字典返回即可，前端无需改动。
