# MySQL 登录报错：缺少 `cryptography`

记录日期：2026-11-15。

## 现象

启动后端时，连接 MySQL 的过程报错：

```text
RuntimeError: 'cryptography' package is required for sha256_password or caching_sha2_password auth methods
```

这条报错来自 MySQL 登录认证。它没有表明股票接口、数据库表或 Redis 本身有问题。

## 原因如何确定

1. 项目的 `requirements.txt` 已经写有 `cryptography>=50,<51`。MySQL 8 使用 `caching_sha2_password` 等认证方式时，当前异步驱动 `asyncmy` 需要这个库。
2. 用项目虚拟环境的 Python 检查后，发现 `asyncmy` 已安装，但 `cryptography` 不存在。**写进依赖文件不代表每个本地虚拟环境都会自动安装。**
3. 这个 `.venv` 由 `uv` 管理，没有安装 `pip`。因此尝试运行 `\.venv\Scripts\python.exe -m pip install ...` 时，得到 `No module named pip`；这只是安装工具不匹配，不是新的 MySQL 故障。

## 本次处理

在项目根目录运行：

```powershell
uv pip install --python .venv\Scripts\python.exe "cryptography>=50,<51"
```

命令的意思：

- `uv pip install`：用现有的 `uv` 安装 Python 包，不要求该虚拟环境自带 `pip`。
- `--python .venv\Scripts\python.exe`：明确安装到**本项目的**虚拟环境，避免装进其他 Python。
- `"cryptography>=50,<51"`：按项目依赖文件规定的版本范围安装。

本次安装得到 `cryptography 50.0.2`；它所需的 `cffi` 和 `pycparser` 也作为依赖安装。没有改动项目代码、依赖文件、数据库模型或数据库数据。

## 验证结果

用 `\.venv\Scripts\python.exe` 导入 `cryptography` 成功，输出版本为 `50.0.2`。随后使用项目已有的数据库配置建立连接，并执行只读的 `SELECT 1`，结果为 `1`。这说明该虚拟环境能够完成这次 MySQL 登录认证和基本查询。

这里验证的是**依赖导入与数据库连接**。本次记录时，尚未由用户重新启动 PyCharm 的完整前后端配置，因此不将完整服务启动或前端页面验收写成已通过。

## 下次遇到时怎么检查

在项目根目录执行：

```powershell
.\.venv\Scripts\python.exe -c "import sys, cryptography; print(sys.executable); print(cryptography.__version__)"
```

这条命令只检查当前虚拟环境和库版本，不连接数据库，也不修改文件。如果提示找不到 `cryptography`，运行上面的 `uv pip install` 命令，然后停止并重新启动 PyCharm 中的后端进程。

重启后再访问原本报错的接口。若出现**不同**的错误，应根据新的报错继续排查；不要通过修改 MySQL 登录方式或数据库密码来掩盖缺少依赖的问题。

## 后续复验与 `pip install` 的区别

用户随后反馈：重新启动后已成功验收，原先的认证报错消失。

在当前终端核对发现，直接输入 `pip` 时使用的是 `D:\space-crunchers\python\Scripts\pip.exe`。`pip show cryptography` 显示它的安装位置为 `D:\space-crunchers\python\Lib\site-packages`；项目后端运行的 Python 则是 `D:\project\mock_stock_trend\.venv\Scripts\python.exe`。这是两个不同的 Python 环境。

因此，即使在**项目根目录**执行 `pip install cryptography`，只要该终端的 `pip` 指向全局 Python，包装进的仍是全局环境。当前项目的 `.venv` 没有自带 `pip`，所以本次用 `uv pip install --python .venv\Scripts\python.exe ...` 明确指定安装目标。以后可以用 `Get-Command pip` 和 `pip --version` 检查 `pip` 指向哪里，再用 `\.venv\Scripts\python.exe -c "import sys; print(sys.executable)"` 检查项目实际运行的 Python。

## 怎样找到项目使用的虚拟环境

本项目的虚拟环境目录是 `D:\project\mock_stock_trend\.venv`；后端使用的解释器是其中的 `Scripts\python.exe`。**虚拟环境**可以简单理解为项目自己的一套 Python 包目录，和电脑上的全局 Python 分开。

- 在 PyCharm 中查看项目的 **Python Interpreter（Python 解释器）**设置，核对解释器的完整路径；再检查后端运行配置是否使用同一个解释器。
- 在项目根目录的 PowerShell 中运行下面的命令，直接打印指定解释器的路径：

```powershell
.\.venv\Scripts\python.exe -c "import sys; print(sys.executable)"
```

这里 `\.venv\Scripts\python.exe` 是要启动的 Python，`-c` 表示执行后面的一小段 Python 代码，`sys.executable` 表示当前正在运行的解释器路径。只在项目根目录执行 `pip`，不能证明它会使用项目虚拟环境。

## 能否激活虚拟环境后执行 `pip install`

**可以，但前提是该虚拟环境里装有 `pip`，而且要核对命令实际指向的环境。**在 PowerShell 中，激活与检查的步骤是：

```powershell
.\.venv\Scripts\Activate.ps1
python -c "import sys; print(sys.executable)"
python -m pip --version
```

第一条让当前终端优先使用 `.venv` 中的命令；第二条确认 `python` 确实指向项目的 `.venv`；第三条检查**这个 Python**能否调用 `pip`。激活环境不等于进入 `.venv` 文件夹，也不保证该环境已安装 `pip`。

本次项目的 `.venv` 中没有 `pip`：找不到 `.venv\Scripts\pip.exe`，运行 `python -m pip --version` 会得到 `No module named pip`。此时单独运行 `pip install cryptography`，PowerShell 可能继续找到全局 `pip`，又把包装错位置。当前直接采用以下命令即可：

```powershell
uv pip install --python .venv\Scripts\python.exe "cryptography>=50,<51"
```

如果将来这个虚拟环境已经有 `pip`，且上面的路径检查正确，可以使用 `python -m pip install "cryptography>=50,<51"`。其中 `python -m pip` 明确让**当前这个 Python**运行自己的 `pip`，比只输入 `pip` 更容易避免装进其他环境。本次依赖已经安装，无须重复执行安装命令。
