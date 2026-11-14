"""在独立 MySQL 测试库中验证新增股票接口与唯一约束。"""

import os
from collections.abc import AsyncIterator
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock

import httpx
import pytest
from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings
from app.core.database import get_session
from app.dependencies import get_market_data_client, get_stock_search_service
from app.main import app
from app.models.daily_price import DailyPrice
from app.models.stock import Stock
from app.service.market_data import DailyBar, MarketDataClient, MarketDataError
from app.service.stock_catalog import StockCandidate
from app.service.stock_search import StockSearchService


@pytest.fixture
def anyio_backend() -> str:
    """异步测试只使用项目运行时采用的 asyncio 事件循环。"""
    return "asyncio"


@pytest.fixture
async def stock_client() -> AsyncIterator[tuple[httpx.AsyncClient, AsyncConnection]]:
    """每个测试独占外层事务，结束时回滚全部测试记录。"""
    settings = get_settings()
    test_database = os.getenv("MYSQL_TEST_DATABASE")
    if test_database is None:
        pytest.skip("未设置 MYSQL_TEST_DATABASE；真实 MySQL 集成测试需显式启用")
    if test_database != f"{settings.mysql_database}_test":
        raise RuntimeError("MYSQL_TEST_DATABASE 必须是学习库名称加 _test")

    # URL.set 只替换数据库名，账号密码仍从本地环境配置读取；
    # 测试请求不会连接当前学习库。测试库须先用现有 Alembic 迁移建好表。
    engine = create_async_engine(
        settings.database_url.set(database=test_database),
        connect_args={"init_command": "SET time_zone = '+00:00'"},
    )
    try:
        async with engine.connect() as connection:
            outer_transaction = await connection.begin()
            session_factory = async_sessionmaker(
                connection,
                expire_on_commit=False,
                join_transaction_mode="create_savepoint",
            )

            async def override_get_session() -> AsyncIterator[AsyncSession]:
                """让 HTTP 请求在测试库的保存点中提交或回滚。"""
                async with session_factory() as session:
                    try:
                        yield session
                        await session.commit()
                    except Exception:
                        await session.rollback()
                        raise

            app.dependency_overrides[get_session] = override_get_session

            # 这组测试验证真实 MySQL 写入和事务，不使用真实外部网站。
            # 假目录只提供测试专用股票，名称由它返回而非请求体决定。
            async def fake_search(*, query: str, market: str) -> list[StockCandidate]:
                if market == "CN" and query == "688385.SH":
                    return [StockCandidate("688385.SH", "复旦微电", "CN", "SSE")]
                if market == "US" and (query == "AAPL" or query.startswith("TEST")):
                    name = "Apple" if query == "AAPL" else query
                    return [StockCandidate(query, name, "US", "NASDAQ")]
                return []

            fake_search_service = AsyncMock(spec=StockSearchService)
            fake_search_service.search.side_effect = fake_search
            app.dependency_overrides[get_stock_search_service] = lambda: (
                fake_search_service
            )
            try:
                # ASGITransport 直接向应用发 HTTP 请求，不启动实际端口。
                transport = httpx.ASGITransport(app=app)
                async with httpx.AsyncClient(
                    transport=transport, base_url="http://testserver"
                ) as client:
                    yield client, connection
            finally:
                app.dependency_overrides.pop(get_stock_search_service, None)
                app.dependency_overrides.pop(get_session, None)
                # 请求中的提交仅释放保存点；最外层事务回滚后，测试数据消失。
                await outer_transaction.rollback()
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_create_us_stock_persists_in_test_database(
    stock_client: tuple[httpx.AsyncClient, AsyncConnection],
) -> None:
    client, connection = stock_client
    response = await client.post(
        "/stocks",
        json={"symbol": " aapl ", "name": "用户误填", "market": "us"},
    )

    assert response.status_code == 201
    assert response.json() == {
        "id": response.json()["id"],
        "symbol": "AAPL",
        "name": "Apple",
        "market": "US",
    }
    assert response.json()["id"] > 0
    stored = (
        await connection.execute(
            select(Stock.symbol, Stock.name, Stock.market).where(
                Stock.id == response.json()["id"]
            )
        )
    ).one()
    assert stored == ("AAPL", "Apple", "US")


@pytest.mark.anyio
async def test_create_stock_without_name_uses_catalog_name(
    stock_client: tuple[httpx.AsyncClient, AsyncConnection],
) -> None:
    """新客户端只传市场和代码，仍能把目录名称写入真实测试库。"""
    client, connection = stock_client
    response = await client.post(
        "/stocks", json={"symbol": "688385.SH", "market": "CN"}
    )

    assert response.status_code == 201
    assert response.json()["name"] == "复旦微电"
    stored_name = (
        await connection.execute(
            select(Stock.name).where(Stock.id == response.json()["id"])
        )
    ).scalar_one()
    assert stored_name == "复旦微电"


@pytest.mark.anyio
async def test_list_stocks_is_paginated_and_sorted_by_newest_id(
    stock_client: tuple[httpx.AsyncClient, AsyncConnection],
) -> None:
    """用真实 MySQL 验证总数、降序、翻页及超出范围的空列表。"""
    client, connection = stock_client
    initial_active_total = (
        await connection.execute(
            select(func.count()).select_from(Stock).where(Stock.archived_at.is_(None))
        )
    ).scalar_one()
    created = []
    for symbol in ("TESTA", "TESTB", "TESTC"):
        response = await client.post(
            "/stocks", json={"symbol": symbol, "name": symbol, "market": "US"}
        )
        assert response.status_code == 201
        created.append(response.json())

    first = await client.get("/stocks?page=1&page_size=2")
    second = await client.get("/stocks?page=2&page_size=2")
    beyond = await client.get("/stocks?page=1000&page_size=2")

    assert first.status_code == second.status_code == beyond.status_code == 200
    assert first.json()["total"] == initial_active_total + 3
    assert first.json()["items"] == [created[2], created[1]]
    assert second.json()["items"][0] == created[0]
    assert beyond.json()["items"] == []


@pytest.mark.anyio
async def test_list_stocks_separates_active_and_archived_in_test_database(
    stock_client: tuple[httpx.AsyncClient, AsyncConnection],
) -> None:
    """用隔离 MySQL 验证两种列表及各自的总数，测试结束后回滚。"""
    client, connection = stock_client
    active_before = (
        await connection.execute(
            select(func.count()).select_from(Stock).where(Stock.archived_at.is_(None))
        )
    ).scalar_one()
    archived_before = (
        await connection.execute(
            select(func.count())
            .select_from(Stock)
            .where(Stock.archived_at.is_not(None))
        )
    ).scalar_one()

    active_stock = await client.post(
        "/stocks",
        json={"symbol": "TESTACTIVE", "name": "正常测试股", "market": "US"},
    )
    archived_stock = await client.post(
        "/stocks",
        json={"symbol": "TESTARCHIVE", "name": "归档测试股", "market": "US"},
    )
    assert active_stock.status_code == archived_stock.status_code == 201

    # 归档操作接口尚未开发：这里仅在测试事务内给一只测试股设置归档时间。
    # fixture 结束时会回滚外层事务，不会留下测试股票或归档时间。
    await connection.execute(
        update(Stock)
        .where(Stock.id == archived_stock.json()["id"])
        .values(archived_at=datetime(2026, 11, 14, 0, 0))
    )

    active = await client.get("/stocks?status=active&page_size=100")
    archived = await client.get("/stocks?status=archived&page_size=100")
    default = await client.get("/stocks?page_size=100")

    assert active.status_code == archived.status_code == default.status_code == 200
    assert active.json()["total"] == default.json()["total"] == active_before + 1
    assert archived.json()["total"] == archived_before + 1
    assert active_stock.json() in active.json()["items"]
    assert archived_stock.json() not in active.json()["items"]
    assert archived_stock.json() in archived.json()["items"]
    assert active_stock.json() not in archived.json()["items"]


@pytest.mark.anyio
async def test_archive_stock_moves_to_archived_list_without_changing_time_twice(
    stock_client: tuple[httpx.AsyncClient, AsyncConnection],
) -> None:
    """真实 MySQL 中首次归档生效，重复归档不重写时间，列表随之变化。"""
    client, connection = stock_client
    active_before = (
        await connection.execute(
            select(func.count()).select_from(Stock).where(Stock.archived_at.is_(None))
        )
    ).scalar_one()
    archived_before = (
        await connection.execute(
            select(func.count())
            .select_from(Stock)
            .where(Stock.archived_at.is_not(None))
        )
    ).scalar_one()
    created = await client.post(
        "/stocks",
        json={"symbol": "TESTARCHIVE", "name": "归档接口测试股", "market": "US"},
    )
    assert created.status_code == 201
    stock_id = created.json()["id"]

    first = await client.patch(f"/stocks/{stock_id}/archive")
    first_time = (
        await connection.execute(select(Stock.archived_at).where(Stock.id == stock_id))
    ).scalar_one()
    second = await client.patch(f"/stocks/{stock_id}/archive")
    second_time = (
        await connection.execute(select(Stock.archived_at).where(Stock.id == stock_id))
    ).scalar_one()

    expected = {"id": stock_id, "symbol": "TESTARCHIVE", "status": "archived"}
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json() == expected
    assert first_time is not None
    assert second_time == first_time

    active = await client.get("/stocks")
    archived = await client.get("/stocks?status=archived")
    assert active.status_code == archived.status_code == 200
    assert active.json()["total"] == active_before
    assert archived.json()["total"] == archived_before + 1
    assert created.json() not in active.json()["items"]
    assert created.json() in archived.json()["items"]


@pytest.mark.anyio
async def test_archive_unknown_stock_returns_404_in_test_database(
    stock_client: tuple[httpx.AsyncClient, AsyncConnection],
) -> None:
    """不存在的编号不会产生股票记录或误报成功。"""
    client, connection = stock_client
    before = (
        await connection.execute(select(func.count()).select_from(Stock))
    ).scalar_one()

    response = await client.patch("/stocks/999999/archive")

    after = (
        await connection.execute(select(func.count()).select_from(Stock))
    ).scalar_one()
    assert response.status_code == 404
    assert response.json() == {"code": 404, "message": "股票不存在"}
    assert after == before


@pytest.mark.anyio
async def test_restore_stock_moves_back_to_active_and_is_repeatable(
    stock_client: tuple[httpx.AsyncClient, AsyncConnection],
) -> None:
    """在隔离 MySQL 中先归档再恢复，重复恢复后仍在正常列表。"""
    client, connection = stock_client
    active_before = (
        await connection.execute(
            select(func.count()).select_from(Stock).where(Stock.archived_at.is_(None))
        )
    ).scalar_one()
    archived_before = (
        await connection.execute(
            select(func.count())
            .select_from(Stock)
            .where(Stock.archived_at.is_not(None))
        )
    ).scalar_one()
    created = await client.post(
        "/stocks",
        json={"symbol": "TESTRESTORE", "name": "恢复接口测试股", "market": "US"},
    )
    assert created.status_code == 201
    stock_id = created.json()["id"]
    assert (await client.patch(f"/stocks/{stock_id}/archive")).status_code == 200

    first = await client.patch(f"/stocks/{stock_id}/restore")
    second = await client.patch(f"/stocks/{stock_id}/restore")
    archived_at = (
        await connection.execute(select(Stock.archived_at).where(Stock.id == stock_id))
    ).scalar_one()

    expected = {"id": stock_id, "symbol": "TESTRESTORE", "status": "active"}
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json() == expected
    assert archived_at is None

    active = await client.get("/stocks")
    archived = await client.get("/stocks?status=archived")
    assert active.status_code == archived.status_code == 200
    assert active.json()["total"] == active_before + 1
    assert archived.json()["total"] == archived_before
    assert created.json() in active.json()["items"]
    assert created.json() not in archived.json()["items"]


@pytest.mark.anyio
async def test_restore_unknown_stock_returns_404_in_test_database(
    stock_client: tuple[httpx.AsyncClient, AsyncConnection],
) -> None:
    """不存在的编号不能凭恢复操作创建股票。"""
    client, connection = stock_client
    before = (
        await connection.execute(select(func.count()).select_from(Stock))
    ).scalar_one()

    response = await client.patch("/stocks/999999/restore")

    after = (
        await connection.execute(select(func.count()).select_from(Stock))
    ).scalar_one()
    assert response.status_code == 404
    assert response.json() == {"code": 404, "message": "股票不存在"}
    assert after == before


@pytest.mark.anyio
async def test_create_cn_stock_normalizes_shanghai_alias(
    stock_client: tuple[httpx.AsyncClient, AsyncConnection],
) -> None:
    client, _ = stock_client
    response = await client.post(
        "/stocks",
        json={"symbol": " 688385.ss ", "name": "复旦微电", "market": "cn"},
    )

    assert response.status_code == 201
    assert response.json()["symbol"] == "688385.SH"
    assert response.json()["market"] == "CN"


@pytest.mark.anyio
async def test_duplicate_stock_returns_409_without_breaking_next_request(
    stock_client: tuple[httpx.AsyncClient, AsyncConnection],
) -> None:
    client, _ = stock_client
    payload = {"symbol": "688385.SH", "name": "复旦微电", "market": "CN"}
    first = await client.post("/stocks", json=payload)
    duplicate = await client.post("/stocks", json=payload)
    next_stock = await client.post(
        "/stocks", json={"symbol": "AAPL", "name": "Apple", "market": "US"}
    )

    assert first.status_code == 201
    assert duplicate.status_code == 409
    assert duplicate.json() == {"code": 409, "message": "该市场的股票代码已存在"}
    assert next_stock.status_code == 201


@pytest.mark.anyio
async def test_archived_stock_cannot_be_registered_again(
    stock_client: tuple[httpx.AsyncClient, AsyncConnection],
) -> None:
    """归档只改变查看状态，原市场和代码仍由原记录占用。"""
    client, connection = stock_client
    created = await client.post("/stocks", json={"symbol": "AAPL", "market": "US"})
    assert created.status_code == 201
    assert (
        await client.patch(f"/stocks/{created.json()['id']}/archive")
    ).status_code == 200

    duplicate = await client.post("/stocks", json={"symbol": "AAPL", "market": "US"})
    count = (
        await connection.execute(
            select(func.count()).select_from(Stock).where(Stock.symbol == "AAPL")
        )
    ).scalar_one()

    assert duplicate.status_code == 409
    assert count == 1


@pytest.mark.anyio
async def test_unknown_catalog_symbol_does_not_write_database(
    stock_client: tuple[httpx.AsyncClient, AsyncConnection],
) -> None:
    """目录中没有精确代码时，不产生只有代码、没有真实身份的记录。"""
    client, connection = stock_client
    before = (
        await connection.execute(select(func.count()).select_from(Stock))
    ).scalar_one()

    response = await client.post("/stocks", json={"symbol": "APPL", "market": "US"})

    after = (
        await connection.execute(select(func.count()).select_from(Stock))
    ).scalar_one()
    assert response.status_code == 404
    assert after == before


@pytest.mark.anyio
@pytest.mark.parametrize(
    "payload",
    [
        {"symbol": "1AAPL", "market": "US"},
        {"symbol": "AAPL", "name": "Apple", "market": "EU"},
        {"symbol": "688385", "name": "复旦微电", "market": "CN"},
        {"symbol": "", "name": "Apple", "market": "US"},
        {"symbol": "AAPL", "name": "Apple"},
    ],
)
async def test_invalid_stock_input_returns_unified_422(
    stock_client: tuple[httpx.AsyncClient, AsyncConnection],
    payload: dict[str, str],
) -> None:
    client, _ = stock_client
    response = await client.post("/stocks", json=payload)

    assert response.status_code == 422
    assert response.json()["code"] == 422
    assert response.json()["message"] == "请求参数不合法"
    assert response.json()["errors"]


@pytest.mark.anyio
async def test_collect_inserts_then_keeps_then_updates_real_mysql_rows(
    stock_client: tuple[httpx.AsyncClient, AsyncConnection],
) -> None:
    """用隔离 MySQL 验证新增、重复采集不重写、旧日线被修正三种情况。"""
    client, connection = stock_client
    created = await client.post(
        "/stocks", json={"symbol": "TESTCOLLECT", "name": "采集测试股", "market": "US"}
    )
    assert created.status_code == 201
    stock_id = created.json()["id"]
    first_bar = DailyBar(
        trade_date=date(2026, 11, 12),
        open_price=Decimal("100.000000"),
        high_price=Decimal("103.000000"),
        low_price=Decimal("99.000000"),
        close_price=Decimal("102.000000"),
        volume=1000,
        currency="USD",
        source="twelvedata",
        adjustment="all",
    )
    fake_market = AsyncMock(spec=MarketDataClient)
    fake_market.fetch_daily_bars.return_value = [first_bar]
    app.dependency_overrides[get_market_data_client] = lambda: fake_market
    try:
        first = await client.post(f"/stocks/{stock_id}/prices/collect?days=1")
        saved = (
            await connection.execute(
                select(
                    DailyPrice.source,
                    DailyPrice.adjustment,
                    DailyPrice.currency,
                    DailyPrice.fetched_at,
                ).where(DailyPrice.stock_id == stock_id)
            )
        ).one()
        original_fetched_at = saved.fetched_at
        second = await client.post(f"/stocks/{stock_id}/prices/collect?days=1")
        same_fetched_at = (
            await connection.execute(
                select(DailyPrice.fetched_at).where(DailyPrice.stock_id == stock_id)
            )
        ).scalar_one()

        fake_market.fetch_daily_bars.return_value = [
            DailyBar(
                trade_date=first_bar.trade_date,
                open_price=first_bar.open_price,
                high_price=first_bar.high_price,
                low_price=first_bar.low_price,
                close_price=Decimal("101.500000"),
                volume=1200,
                currency="USD",
                source="twelvedata",
                adjustment="all",
            )
        ]
        third = await client.post(f"/stocks/{stock_id}/prices/collect?days=1")
        stored = (
            await connection.execute(
                select(DailyPrice.close_price, DailyPrice.volume).where(
                    DailyPrice.stock_id == stock_id
                )
            )
        ).one()
    finally:
        app.dependency_overrides.pop(get_market_data_client, None)

    assert first.status_code == second.status_code == third.status_code == 200
    assert first.json() == {
        "stock_id": stock_id,
        "symbol": "TESTCOLLECT",
        "inserted": 1,
        "updated": 0,
        "unchanged": 0,
    }
    assert second.json()["inserted"] == 0
    assert second.json()["updated"] == 0
    assert second.json()["unchanged"] == 1
    assert third.json()["inserted"] == 0
    assert third.json()["updated"] == 1
    assert third.json()["unchanged"] == 0
    assert saved.source == "twelvedata"
    assert saved.adjustment == "all"
    assert saved.currency == "USD"
    assert original_fetched_at == same_fetched_at
    assert stored.close_price == Decimal("101.500000")
    assert stored.volume == 1200
    assert (
        await connection.execute(
            select(func.count())
            .select_from(DailyPrice)
            .where(DailyPrice.stock_id == stock_id)
        )
    ).scalar_one() == 1


@pytest.mark.anyio
async def test_old_unadjusted_bar_blocks_collection_until_explicit_cleanup(
    stock_client: tuple[httpx.AsyncClient, AsyncConnection],
) -> None:
    """旧 none 日线不能被新 all 日线悄悄覆盖；清理后才能重新采集。"""
    client, connection = stock_client
    created = await client.post("/stocks", json={"market": "US", "symbol": "TESTBASIS"})
    assert created.status_code == 201
    stock_id = created.json()["id"]
    await connection.execute(
        insert(DailyPrice),
        [
            {
                "stock_id": stock_id,
                "trade_date": date(2026, 11, 12),
                "open_price": Decimal("100.000000"),
                "high_price": Decimal("102.000000"),
                "low_price": Decimal("99.000000"),
                "close_price": Decimal("101.000000"),
                "volume": 1000,
                "currency": "USD",
                "source": "twelvedata",
                "adjustment": "none",
            }
        ],
    )
    adjusted = DailyBar(
        trade_date=date(2026, 11, 12),
        open_price=Decimal("99.000000"),
        high_price=Decimal("101.000000"),
        low_price=Decimal("98.000000"),
        close_price=Decimal("100.000000"),
        volume=1000,
        currency="USD",
        source="twelvedata",
        adjustment="all",
    )
    fake_market = AsyncMock(spec=MarketDataClient)
    fake_market.fetch_daily_bars.return_value = [adjusted]
    app.dependency_overrides[get_market_data_client] = lambda: fake_market
    try:
        conflict = await client.post(f"/stocks/{stock_id}/prices/collect?days=1")
        stored_before = (
            await connection.execute(
                select(DailyPrice.adjustment).where(DailyPrice.stock_id == stock_id)
            )
        ).scalar_one()

        # 只在隔离测试事务中演示用户已允许的清理步骤。
        await connection.execute(
            delete(DailyPrice).where(
                DailyPrice.stock_id == stock_id, DailyPrice.adjustment == "none"
            )
        )
        recollected = await client.post(f"/stocks/{stock_id}/prices/collect?days=1")
        stored_after = (
            await connection.execute(
                select(DailyPrice.adjustment).where(DailyPrice.stock_id == stock_id)
            )
        ).scalar_one()
    finally:
        app.dependency_overrides.pop(get_market_data_client, None)

    assert conflict.status_code == 409
    assert stored_before == "none"
    assert recollected.status_code == 200
    assert recollected.json()["inserted"] == 1
    assert stored_after == "all"


@pytest.mark.anyio
async def test_collect_archived_stock_never_calls_market_source(
    stock_client: tuple[httpx.AsyncClient, AsyncConnection],
) -> None:
    """归档后的股票不能采集，也不应浪费外部数据源调用额度。"""
    client, connection = stock_client
    created = await client.post(
        "/stocks",
        json={"symbol": "TESTARCHCOLL", "name": "归档采集测试", "market": "US"},
    )
    assert created.status_code == 201
    stock_id = created.json()["id"]
    assert (await client.patch(f"/stocks/{stock_id}/archive")).status_code == 200

    fake_market = AsyncMock(spec=MarketDataClient)
    app.dependency_overrides[get_market_data_client] = lambda: fake_market
    try:
        response = await client.post(f"/stocks/{stock_id}/prices/collect?days=1")
    finally:
        app.dependency_overrides.pop(get_market_data_client, None)

    assert response.status_code == 409
    assert response.json() == {"code": 409, "message": "已归档股票不可采集行情"}
    fake_market.fetch_daily_bars.assert_not_awaited()
    assert (
        await connection.execute(
            select(func.count())
            .select_from(DailyPrice)
            .where(DailyPrice.stock_id == stock_id)
        )
    ).scalar_one() == 0


@pytest.mark.anyio
async def test_collect_source_failure_does_not_save_prices(
    stock_client: tuple[httpx.AsyncClient, AsyncConnection],
) -> None:
    """行情源失败时返回 502，并确认测试库没有出现半截行情。"""
    client, connection = stock_client
    created = await client.post(
        "/stocks", json={"symbol": "TESTFAILCOLL", "name": "失败测试股", "market": "US"}
    )
    assert created.status_code == 201
    stock_id = created.json()["id"]

    fake_market = AsyncMock(spec=MarketDataClient)
    fake_market.fetch_daily_bars.side_effect = MarketDataError("行情网站请求失败")
    app.dependency_overrides[get_market_data_client] = lambda: fake_market
    try:
        response = await client.post(f"/stocks/{stock_id}/prices/collect?days=2")
    finally:
        app.dependency_overrides.pop(get_market_data_client, None)

    assert response.status_code == 502
    assert response.json() == {"code": 502, "message": "行情网站请求失败"}
    assert (
        await connection.execute(
            select(func.count())
            .select_from(DailyPrice)
            .where(DailyPrice.stock_id == stock_id)
        )
    ).scalar_one() == 0


@pytest.mark.anyio
async def test_price_history_returns_latest_rows_in_ascending_order(
    stock_client: tuple[httpx.AsyncClient, AsyncConnection],
) -> None:
    """真实 MySQL 先筛最近两天，再按日期从早到晚返回；归档后仍可读。"""
    client, connection = stock_client
    created = await client.post("/stocks", json={"market": "US", "symbol": "TESTPRICE"})
    assert created.status_code == 201
    stock_id = created.json()["id"]

    await connection.execute(
        insert(DailyPrice),
        [
            {
                "stock_id": stock_id,
                "trade_date": date(2026, 11, day),
                "open_price": Decimal(f"{100 + day}.000000"),
                "high_price": Decimal(f"{101 + day}.000000"),
                "low_price": Decimal(f"{99 + day}.000000"),
                "close_price": Decimal(f"{100 + day}.500000"),
                "volume": 1000 * day,
                "currency": "USD",
                "source": "twelvedata",
                "adjustment": "none",
            }
            for day in (11, 12, 13)
        ],
    )

    response = await client.get(f"/stocks/{stock_id}/prices?days=2")
    assert response.status_code == 200
    assert response.json()["symbol"] == "TESTPRICE"
    assert response.json()["market"] == "US"
    assert [item["trade_date"] for item in response.json()["items"]] == [
        "2026-11-12",
        "2026-11-13",
    ]
    assert [item["close_price"] for item in response.json()["items"]] == [
        "112.500000",
        "113.500000",
    ]

    assert (await client.patch(f"/stocks/{stock_id}/archive")).status_code == 200
    archived_response = await client.get(f"/stocks/{stock_id}/prices?days=1")
    assert archived_response.status_code == 200
    assert [item["trade_date"] for item in archived_response.json()["items"]] == [
        "2026-11-13"
    ]


@pytest.mark.anyio
async def test_price_history_empty_for_stock_without_collection(
    stock_client: tuple[httpx.AsyncClient, AsyncConnection],
) -> None:
    """股票存在但还没采集日线时不报 404。"""
    client, _ = stock_client
    created = await client.post("/stocks", json={"market": "US", "symbol": "TESTEMPTY"})
    assert created.status_code == 201

    response = await client.get(f"/stocks/{created.json()['id']}/prices")
    assert response.status_code == 200
    assert response.json()["items"] == []
