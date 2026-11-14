# 股票趋势分析项目前端 S0 交付

## 使用方式
1. 将本压缩包中的 `frontend/` 文件夹复制到已验收 P1 后端项目根目录，与 `app/` 和 `docs/` 同级。
2. 将 `docs/frontend/` 的三份设计文件复制到后端项目的 `docs/frontend/`。
3. 依照 `frontend/README.md` 的 Windows / PowerShell 命令安装依赖、生成 API 类型并启动前端。

## 本次交付边界
- 已建立三态主题基础、统一请求错误层、Vite 代理、健康检查和业务路由占位。
- 未开发股票页面、K 线或指标，也未修改后端。
- 当前环境无法连接 npm 仓库，未执行 pnpm 安装、TypeScript 类型检查、Vitest、ESLint 或 Vite build。用户本地运行后才能宣布 S0 验收通过。
- 没有伪造 `pnpm-lock.yaml`；第一次联网安装生成后应提交锁文件。

## 2026-11-15 本地复核

- 已在本项目中安装 pnpm 10.0.0 声明的依赖并生成锁文件；锁文件重复安装通过。
- OpenAPI 类型生成、TypeScript 类型检查、ESLint、Prettier、3 个 Vitest 测试和 Vite 构建均已运行；ESLint 有 21 条排版警告，构建有首包体积警告。
- 浏览器中已核对本地代理健康检查、占位路由、主题切换和窄屏布局。
- 已配置前端 CI；用户手动复核和 GitHub 远程结果仍待完成。
