# Stock Trend Lab · Vue 前端

前端使用 Vue 3、TypeScript、Vite、Vue Router、Element Plus 和 Axios。S0 工程骨架已验收；S1 股票追踪的核心流程已通过手动验收，异常与边界场景仍需补测。S2 股票详情、日线采集及服务异常的核心流程已通过手动验收。S3 趋势分析已接入，主要流程已通过自动检查和手动验收；剩余边界场景见下方验收记录。

## 已接入的页面

- `/stocks`：正常追踪股票的列表，支持市场、关键词和分页筛选；条件保存在 URL 中。
- `/stocks/add`：按代码或名称搜索外部股票目录，再选择股票加入追踪。
- `/stocks/archived`：查看已归档股票并恢复追踪。
- `/stocks/:stockId`：股票详情、已保存日线图表与手动采集。

股票接口由 `src/features/stocks/api.ts` 调用，统一使用 `src/api/http.ts` 中的 Axios 客户端。请求和响应类型以 `../docs/openapi.yaml` 生成的 `src/api/generated/schema.d.ts` 为准，不手工修改生成文件。

## 本机启动

先在项目根目录启动后端：

```powershell
.venv\Scripts\python -m app.main
```

这个命令让后端监听 `127.0.0.1:18000`。另开一个终端，进入 `frontend/` 后运行：

```powershell
corepack pnpm install --frozen-lockfile
corepack pnpm gen:api
corepack pnpm dev
```

`corepack pnpm` 使用 `package.json` 指定的 pnpm 10.0.0；`--frozen-lockfile` 要求依赖与已提交的锁文件一致；`gen:api` 根据后端 OpenAPI 文档生成 TypeScript 类型；`dev` 启动本机前端。浏览器打开 `http://127.0.0.1:5173/`。

开发时，浏览器对 `/api/*` 的请求由 Vite 转发到本机后端。`/api/health` 仅说明后端 HTTP 进程可访问，不代表数据库或 Redis 已检查通过。

## 可选：局域网调试

只有在确实需要让同一可信局域网中的其他设备查看开发页面时，才在 `frontend/` 运行：

```powershell
corepack pnpm dev:lan
```

该命令让 Vite 监听 `0.0.0.0:5173`。其他设备使用开发电脑的局域网 IPv4 地址访问，例如 `http://<开发电脑IPv4>:5173/`。Vite 的 `/api` 代理也会对这些设备生效，因此它们能够调用后端管理接口；在完成鉴权和权限控制之前，不要在不可信网络或面向多人时使用。不要开放 MySQL、Redis 或后端 18000 端口，也不要把密钥放入 `VITE_*` 环境变量。此模式只是开发调试方式，不是部署方式。

## 质量检查

在 `frontend/` 执行：

```powershell
corepack pnpm lint
corepack pnpm typecheck
corepack pnpm test
corepack pnpm format:check
corepack pnpm build
```

这些命令依次检查代码规则、TypeScript 类型、单元测试、格式和正式构建。仓库 CI 也运行相同的前端检查。S1 的运行与手动验收结果记录在[前端开发计划](../docs/frontend/03-开发计划与验收标准.md)。

成功响应直接使用后端业务结构，没有通用 `data` 外壳；失败时优先展示 `error_code` 对应的业务提示或后端 `message`。`POST /stocks` 只提交市场和代码，股票名称由后端重新核对。归档前会弹出确认框，归档或恢复后重新请求列表。

## S2：日线详情与异常提示

`/stocks/:stockId` 显示股票信息、已保存的日线 K 线和成交量。用户可手动发起采集；采集成功后，页面重新请求已保存日线。采集请求不会自动重试，超时后应先刷新行情，确认服务器是否已写入数据。

股票详情和已保存日线的 GET 请求只在网络、超时或无业务错误码的代理错误时有限重试。图表绘制时才把价格字符串转为数字；交易日期不做时区换算。详细操作与验收项见[S2 开发与验收说明](../docs/04-S2开发与验收说明.md)。

## S3：趋势分析与历史快照

股票详情页在采集区域下方增加独立的“分析条数”和已保存批次列表。运行分析会把 `days` 放进 JSON 请求体；新建返回 201，同条件重算返回 200。分析 POST 不自动重试，断线或超时后先刷新批次列表确认结果。

从批次列表打开 `/stocks/:stockId/analysis/:runId` 可查看后端保存的逐日指标。图表展示收盘价与 MA5/MA20、RSI14、MACD 柱值，空指标保持为空；交易日期不转换时区，计算时间按浏览器本地时间显示。归档股票仍可查看历史批次，但不能运行新分析。详细结果和未手测范围见 [S3 开发与验收说明](../docs/05-S3开发与验收说明.md)。
