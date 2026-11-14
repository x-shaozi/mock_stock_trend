"""不连接数据库，检查正常和归档两种列表是否使用正确的查询条件。"""

from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.dialects import mysql
from sqlalchemy.ext.asyncio import AsyncSession

from app.repository.stock import StockRepository
from app.service.stock import StockService


@pytest.fixture
def anyio_backend() -> str:
    """让异步测试使用项目运行时的 asyncio。"""
    return "asyncio"


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("status", "where_clause"),
    [
        ("active", "stocks.archived_at IS NULL"),
        ("archived", "stocks.archived_at IS NOT NULL"),
    ],
)
async def test_count_and_page_use_the_same_status_filter(
    status: str, where_clause: str
) -> None:
    """总数与当前页必须筛选同一类股票，避免数字与列表对不上。"""
    session = AsyncMock(spec=AsyncSession)
    count_result = Mock()
    count_result.scalar_one.return_value = 2
    page_result = Mock()
    page_result.scalars.return_value.all.return_value = []
    session.execute.side_effect = [count_result, page_result]
    repository = StockRepository(session)

    assert await repository.count(status=status) == 2
    assert await repository.list_page(offset=10, limit=5, status=status) == []

    # execute 收到的是 SQLAlchemy 查询对象；编译为 MySQL SQL 后核对条件。
    # 这里只检查要执行的 SQL，不建立数据库连接。
    statements = [call.args[0] for call in session.execute.await_args_list]
    sql_texts = [
        str(statement.compile(dialect=mysql.dialect())) for statement in statements
    ]
    assert len(sql_texts) == 2
    assert all(f"WHERE {where_clause}" in sql for sql in sql_texts)
    assert "ORDER BY stocks.id DESC" in sql_texts[1]


@pytest.mark.anyio
async def test_service_passes_status_to_both_queries() -> None:
    """业务层计算第二页偏移量，并给两个仓储查询传同一个状态。"""
    repository = AsyncMock(spec=StockRepository)
    repository.count.return_value = 4
    repository.list_page.return_value = []
    service = StockService(repository)

    stocks, total = await service.list_stocks(page=2, page_size=5, status="archived")

    assert stocks == []
    assert total == 4
    repository.count.assert_awaited_once_with(
        status="archived", market=None, keyword=None
    )
    repository.list_page.assert_awaited_once_with(
        offset=5, limit=5, status="archived", market=None, keyword=None
    )


@pytest.mark.anyio
async def test_count_and_page_share_market_and_keyword_predicates() -> None:
    """市场、关键词、归档状态必须同时限制总数与当前页。"""
    session = AsyncMock(spec=AsyncSession)
    count_result = Mock()
    count_result.scalar_one.return_value = 1
    page_result = Mock()
    page_result.scalars.return_value.all.return_value = []
    session.execute.side_effect = [count_result, page_result]
    repository = StockRepository(session)

    assert await repository.count(status="archived", market="US", keyword="AAPL") == 1
    assert (
        await repository.list_page(
            offset=20, limit=20, status="archived", market="US", keyword="AAPL"
        )
        == []
    )

    statements = [call.args[0] for call in session.execute.await_args_list]
    compiled = [statement.compile(dialect=mysql.dialect()) for statement in statements]
    # 忽略 SQL 的 SELECT/ORDER BY 差别，比较完整 WHERE 谓词及绑定值。
    assert len(compiled) == 2
    conditions = [
        str(statement.whereclause.compile(dialect=mysql.dialect()))
        for statement in statements
    ]
    assert conditions[0] == conditions[1]
    assert "stocks.archived_at IS NOT NULL" in conditions[0]
    assert "stocks.market" in conditions[0]
    assert "lower(stocks.symbol) LIKE lower(" in conditions[0]
    assert "lower(stocks.name) LIKE lower(" in conditions[0]
    assert all("US" in c.params.values() for c in compiled)
    assert all("%AAPL%" in c.params.values() for c in compiled)


@pytest.mark.anyio
async def test_keyword_escapes_like_wildcards() -> None:
    """搜索输入的百分号、下划线和反斜线均不能扩大匹配范围。"""
    session = AsyncMock(spec=AsyncSession)
    count_result = Mock()
    count_result.scalar_one.return_value = 0
    session.execute.return_value = count_result
    repository = StockRepository(session)

    await repository.count(status="active", keyword=r"A%_\B")
    statement = session.execute.await_args.args[0]
    compiled = statement.compile(dialect=mysql.dialect())
    assert r"%A!%!_\B%" in compiled.params.values()

    await repository.count(status="active", keyword="A!%")
    next_statement = session.execute.await_args.args[0]
    next_compiled = next_statement.compile(dialect=mysql.dialect())
    assert "%A!!!%%" in next_compiled.params.values()


@pytest.mark.anyio
async def test_service_passes_market_and_keyword_to_both_queries() -> None:
    """Service 不应只过滤列表而忘记过滤 total。"""
    repository = AsyncMock(spec=StockRepository)
    repository.count.return_value = 1
    repository.list_page.return_value = []
    service = StockService(repository)

    stocks, total = await service.list_stocks(
        page=3, page_size=10, status="active", market="CN", keyword="微电"
    )
    assert stocks == []
    assert total == 1
    repository.count.assert_awaited_once_with(
        status="active", market="CN", keyword="微电"
    )
    repository.list_page.assert_awaited_once_with(
        offset=20, limit=10, status="active", market="CN", keyword="微电"
    )
