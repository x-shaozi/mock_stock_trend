"""${message}。"""

# 这是生成未来迁移文件的模板，不是直接运行的 Python 文件。
# 模板中的美元大括号占位符会替换为迁移说明、编号和操作代码。

import sqlalchemy as sa

from alembic import op

# 当前版本号和上一版本号会形成一条可追踪的迁移链。
revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    # 未来迁移向前执行时，使用生成时填入的操作代码。
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    # 未来迁移向后回退时，使用生成时填入的操作代码。
    ${downgrades if downgrades else "pass"}
