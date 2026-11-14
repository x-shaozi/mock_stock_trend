# mock_stock_trend

基于 FastAPI 的异步股票趋势 API。股票管理已使用 MySQL；Redis 客户端已预留，当前业务接口尚未使用。

## 本地启动

需要 Python 3.11 或更新版本。使用股票接口时需要可用的 MySQL 8；当前接口不执行 Redis 命令，因此暂时不要求启动 Redis 服务。健康检查不连接 MySQL 或 Redis。

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
.venv\Scripts\python -m app.main
```

从项目根目录运行以上命令。IDE 中应选择“运行模块”并填写 `app.main`，工作目录设为项目根目录。在 `.env` 中填写本地连接参数。访问 `http://127.0.0.1:18000/health` 检查服务，访问 `http://127.0.0.1:18000/docs` 查看接口文档。

## 选择要追踪的股票

先调用 `GET /stocks/search?market=CN&query=688385`，也可以把 `query` 换成股票名称；美股把 `market` 改为 `US`。搜索只返回候选，不会写数据库。选中结果后，调用 `POST /stocks`，请求体只需提交搜索结果中的 `market` 和 `symbol`，例如 `{"market":"CN","symbol":"688385.SH"}`。服务端会再次核对代码并填写名称，然后把股票加入本地追踪列表。旧客户端仍可提交 `name`，但保存时使用股票目录中的名称。`GET /stocks` 查看已追踪股票。

已采集的日线可用 `GET /stocks/{stock_id}/prices?days=90` 查看。`stock_id` 是 `POST /stocks` 返回的编号；`days` 可填 1～260，默认 90。接口从数据库取最近的日线，按交易日从早到晚返回，不会再次联网采集；价格在 JSON 中是保留小数精度的字符串。尚未采集时返回空的 `items` 列表。

采集 A 股日线不需要额外密钥。采集美股前，登录 Twelve Data 控制台取得个人 API Key，在本机 `.env` 中增加 `TWELVE_DATA_API_KEY=你的密钥`，保存后重启服务。不要把真实密钥放进 `.env.example`、代码或聊天消息。`POST /stocks/{stock_id}/prices/collect?days=90` 使用已登记股票的编号采集最近 90 条完整日线；`days` 可填 1～260。A 股保存腾讯前复权价格（`adjustment=qfq`），美股保存 Twelve Data 调整后价格（`adjustment=all`），供 v1 趋势规则计算。为避免收盘前价格入库，当前版本只保存交易日期早于当前 UTC 日期的记录，因此最新交易日可能晚一天入库。重复采集时，相同记录保持原样，变化的记录会更新；旧的 `adjustment=none` 行不能与新口径混合，须先清理旧日线再重新采集。

已存日线达到指定条数后，可调用 `POST /stocks/{stock_id}/analysis-runs`，请求体如 `{"days":90}`。`days` 默认 90，范围 35～260；本接口只分析数据库中最近恰好 `days` 条日线，不访问行情网站。少于请求条数时返回 409，可先调用采集接口补足。首次分析返回 201，同一股票、天数、结束日期和规则版本再次分析会更新原批次并返回 200。响应包含批次编号、实际日期范围、来源、调整方式和最后一天的指标与趋势评分；逐日结果保存在 `analysis_results`，前 34 天用于预热而没有完整评分。行情日后被修正时，需要再次调用本接口重算，旧结果不会自动变化。

取得响应中的 `run_id` 后，可调用 `GET /stocks/{stock_id}/analysis-runs/{run_id}` 查看这轮分析已保存的全部逐日结果，按交易日期从早到晚排列。价格和指标在 JSON 中以字符串保留小数精度；前 34 天尚未得到的评分等字段为 `null`。此接口只读取保存时的结果，不访问行情网站，也不会因原始日线变化而自动重算；归档股票的旧分析仍可查看。`computed_at` 使用 UTC 时间。

忘记 `run_id` 时，可先调用 `GET /stocks/{stock_id}/analysis-runs?page=1&page_size=20` 查看这只股票保存过哪些分析批次。`page` 从 1 开始，`page_size` 为 1～100，默认分别是 1 和 20。响应包含 `items`、`total`、`page` 和 `page_size`；每条批次显示编号、分析天数、日期范围、来源、价格调整方式、规则版本和 UTC 计算时间，不包含每日指标。列表按计算时间从新到旧排列；时间相同时编号较大的在前。没有批次时返回空列表；已归档股票的历史批次仍可查看。

## 项目结构

- `app/routers/`：HTTP 路由、参数与响应模型。
- `app/service/`：业务规则与流程。
- `app/repository/`：数据库访问。
- `app/models/`：SQLAlchemy 数据库模型；当前定义了 `Stock`、`DailyPrice`、`AnalysisRun` 和 `AnalysisResult`。
- `app/core/`：配置、异步数据库会话和 Redis 客户端提供函数。
- `app/dependencies.py`：集中声明 FastAPI 依赖，并组装仓储与业务服务。
- `app/schemas/`：请求与响应模型。
- `tests/`：自动化测试。
- `docs/openapi.yaml`：公开 API 契约。
- `alembic/`：数据库表结构迁移；当前有四份建表迁移和一份股票归档字段迁移。
- `.github/workflows/ci.yml`：自动运行检查和测试。

新增数据库表时，先按仓库约定取得人工确认，再编写模型和 Alembic 迁移；不要用 `create_all()` 在应用启动时直接改表。`stocks`、`daily_prices`、`analysis_runs`、`analysis_results` 四份建表迁移和 `stocks.archived_at` 字段迁移已在本地学习数据库执行；其他环境是否已迁移，应运行 `python -m alembic current` 查看。

HTTP 错误使用统一的 `code`、`message` 格式；参数错误还包含 `errors`。日志默认输出到标准错误流，使用 `LOG_LEVEL` 环境变量调整级别。所有数据库、Redis 和外部接口等 I/O 密集型操作均按 `AGENTS.md` 使用异步接口。应用的异步 MySQL 连接在建立时将会话时区设为 UTC；`trade_date` 仍是交易所当地日期。

## 检查

```powershell
.venv\Scripts\python -m pytest tests -v
.venv\Scripts\python -m ruff check .
.venv\Scripts\python -m ruff format --check .
```

## 远程检查

GitHub Actions 在推送代码或提交合并请求后，分别用 Python 3.11 和 3.14 运行 Ruff 与测试。每个任务会启动临时 MySQL 8，先在隔离测试库执行 Alembic 迁移，再运行包含数据库集成测试的完整测试集；不会连接本机的学习库，也不需要行情网站的个人密钥。

首次运行前，在 GitHub 仓库的 **Settings → Secrets and variables → Actions** 中创建名为 `CI_MYSQL_PASSWORD` 的 Repository secret，填入专门用于 CI 的随机密码。工作流只通过环境变量读取它，不把密码写进仓库。测试库名固定为 `stock_ci_test`，基础名称为 `stock_ci`，满足测试夹具要求的“基础名称加 `_test`”。远程是否真正通过，应在仓库 **Actions** 页面分别查看两个 Python 版本的日志；工作流文件存在不代表运行已经成功。
