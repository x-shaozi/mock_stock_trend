# 后端 P1 兼容性增强：变更与验证报告

日期：2026-11-15

## 范围

1. `GET /stocks/{stock_id}`：按主键查询股票详情，包含 `status`、`created_at`、`archived_at`。已归档股票可查询，UTC 时间带 `Z`。
2. `GET /stocks`：新增可选 `market`、`keyword`；在数据库中执行筛选和分页，`total` 与 `items` 使用同一套 SQL WHERE 条件。`keyword` 修剪空格，包含匹配时转义 SQL LIKE 特殊字符。
3. 错误响应可选 `error_code`：有业务含义的 404/409/502 返回稳定字符串；旧的 `code`、`message`、HTTP 状态码均保留；框架级 404、422、500 的旧结构保留。

新增/修改的公共接口均已更新 `docs/openapi.yaml`，另外有 `docs/前端P1接口增强说明.md`。

## 未改动范围

- 没有修改 `app/models/` 数据库模型、Alembic 迁移、外部数据供应商、技术指标计算规则。
- 没有新增 Redis 使用、身份认证、限流或公网部署配置。
- 没有改动原始 ZIP 文件；交付文件为独立的修改副本。

## 验证结果

- `python -m compileall -q app tests`：通过。
- 基于本地可用 FastAPI/Pydantic/SQLAlchemy 的 HTTP 契约及纯单元测试：**132 passed, 34 skipped**。
  - 因当前容器未提供 `redis` 和 `asyncmy`，测试入口临时使用隔离的 Redis/数据库引擎替身，仅让不访问真实数据库的测试可以执行；替身**没有写入交付代码**。
  - 34 个跳过项为依赖独立 MySQL 测试库的集成测试；未声明已经完成真实 MySQL 验证。
- `tests/test_openapi.py`：在当前可用 FastAPI/Pydantic 版本下通过，文档与 `app.openapi()` 一致。
- `ruff check .` / `ruff format --check .`：**未运行**。当前环境没有 Ruff，且无法联网安装；需要在原项目已配置的开发环境或 CI 中执行。
- 尚未进行真实 Redis、MySQL、外部行情、Docker、生产部署验证。
- OpenAPI 用本地 FastAPI/Pydantic 重新生成，可能出现版本造成的非业务 Schema 差异（如 Decimal 模式约束）；请在既有 CI 中检查依赖版本稳定性。

## 你在本地的下一步

1. 备份已验收分支；在新 Git 分支上应用补丁或审阅修改版项目。**不要直接覆盖当前已验收的工作目录。**
2. 使用现有 venv 安装 `requirements-dev.txt`，执行 `python -m ruff check .`、`python -m ruff format --check .`、`python -m pytest tests/test_openapi.py tests/test_stock_api_contract.py tests/test_stock_status_filter.py -v`。
3. 确保 `MYSQL_TEST_DATABASE` 明确指向已迁移的隔离测试数据库，执行 `python -m pytest tests -v` 完成真实数据库集成测试。
4. 检查 Swagger UI 中的新详情和筛选参数；确认通过后再让 Vue 端消费新的 OpenAPI 类型。
5. 公网发布前必须另外完成鉴权/授权、限流、生产安全配置和行情数据授权审核。
