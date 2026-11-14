# Vue 前端协作规范（S0 基线）

## 作用范围

仅约束 `frontend/`；不得修改已验收的 `app/`、`alembic/`、后端测试或 `docs/openapi.yaml`，除非用户另外明确授权。根目录 `AGENTS.md` 对整个项目仍然有效。

## 技术栈和边界

- Vue 3、TypeScript、Vite、Vue Router、Element Plus、ECharts，单页应用。
- Vue SFC 使用 `<script setup lang="ts">`，Props/Emits 明确类型。
- `src/api/http.ts` 处理网络与错误规范；页面和图表组件不得散落 Axios 配置。
- `src/api/generated/` 由后端 `docs/openapi.yaml` 生成，不手改生成类型。
- 后端已实现的接口契约优先于 UI 假设。不得模拟不存在的实时行情或交易能力。
- 价格 Decimal 字符串在 API 模型保持字符串；图表转换只在适配层进行。`trade_date` 不做时区换算；UTC 时间戳在显示层转换。
- 前端不计算或重定义 MA、RSI、MACD 业务口径，不能将旧分析批次当作实时结果。

## UI 与安全

- 支持浅色、深色、跟随系统三态；持久化用户选择；Element Plus 和图表颜色同步。
- 允许本地开发代理，公开部署时使用同源 /api 反向代理。
- 任何 `VITE_*` 变量均视作对用户公开，禁止存放行情 API Key、数据库密码、Token。
- 未完成认证、授权、限流及数据许可前，禁止将管理接口直接开放公网。
- 未对接真实数据前，所有示例/占位内容必须显式标注。

## 质量门禁

- 每次改动运行 `pnpm lint`、`pnpm typecheck`、`pnpm test`、`pnpm build`；需要格式校验时运行 `pnpm format:check`。
- 关键交互覆盖正常、空、边界、错误四类状态。修复 Bug 时优先建立回归测试。
- 不能把未执行的测试、依赖安装和构建当作已经验证通过。
- 所有 UI / API 改动更新相应设计文档与测试；不要擅自修改后端源码来迎合前端错误调用。

## 分阶段实施

S0 只实现基础工程、主题、代理、健康检查和占位路由。S1 股票追踪；S2 日线行情与图表；S3 趋势指标、分析批次；S4 端到端与部署验收。
