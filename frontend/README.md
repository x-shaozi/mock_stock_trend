# Stock Trend Lab · Vue 前端（S0）

本目录是基于 **mock_stock_trend P1 已验收接口**设计的前端工程起点。S0 只有基础导航、三态主题切换、统一 Axios 层、HTTP 健康检查以及预留路由；尚无股票业务页面。2026-11-15 已完成本地安装、自动检查、构建、浏览器联调、用户手动验收和远程 CI。

## 放置方式

将本 `frontend/` 复制到已验收后端的仓库根目录（与 `app/`、`docs/` 同级），不要替换现有后端文件。脚本 `pnpm gen:api` 读取相邻的 `../docs/openapi.yaml`。

## Windows / PowerShell 快速启动

后端继续用 PyCharm 从仓库根目录运行 `python -m app.main`，确认 `http://127.0.0.1:18000/health` 返回 `{"status":"ok"}`。前端在 VS Code 中打开 `frontend/`，运行：

```powershell
# Node.js 22.12+；Corepack 会读取 package.json 指定的 pnpm 10.0.0。
corepack pnpm install --frozen-lockfile
corepack pnpm gen:api
corepack pnpm dev
```

浏览器访问 `http://127.0.0.1:5173`。如果系统没有 Corepack，可按照 pnpm 官方文档安装 pnpm 10.0.0。`--frozen-lockfile` 表示严格使用已提交的 `pnpm-lock.yaml`，依赖声明与锁文件不一致时安装会失败。

## 接口与代理

- 浏览器访问 `/api/health`，Vite 转发到 `http://127.0.0.1:18000/health`。
- `src/api/http.ts` 统一处理网络失败和 P1 可选 `error_code`。
- 成功响应使用 FastAPI 业务 Schema，**没有**额外 `{ data: ... }` 包装。
- OpenAPI 类型生成：`pnpm gen:api`。后续业务 API 使用 `src/api/generated/schema.d.ts`，不得手动篡改。
- Vite 代理只用于开发。部署时由 Nginx/网关配置同源 `/api` 反向代理与前端路由回退。

## 命令

```powershell
pnpm lint
pnpm typecheck
pnpm test
pnpm format:check
pnpm build
```

## 注意

- `/health` 只验证 HTTP 进程，不保证 MySQL / Redis 可用。
- S0 占位路由不表示股票业务已完成。
- `pnpm-lock.yaml` 已生成；仓库 CI 已通过[首次前端运行](https://github.com/x-shaozi/mock_stock_trend/actions/runs/43655968226)。
- 本地构建通过，但 Vite 提示首包超过 500 kB；S1 引入真实页面时应按路由拆分代码。
- 公开部署前仍需完成认证、权限、限流、HTTPS、行情数据授权等工作。
