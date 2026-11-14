"""在隔离 MySQL 测试库验证一轮趋势分析的保存、重算与错误响应。"""

import os
from collections.abc import AsyncIterator
from datetime import date, datetime, timedelta
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import func, insert, select, update
from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.database import get_session
from app.main import app
from app.models.analysis_result import AnalysisResult
from app.models.analysis_run import AnalysisRun
from app.models.daily_price import DailyPrice
from app.models.stock import Stock


@pytest.fixture
def anyio_backend() -> str:
    """异步测试使用与应用相同的 asyncio 事件循环。"""
    return "asyncio"


@pytest.fixture
async def analysis_client() -> AsyncIterator[tuple[httpx.AsyncClient, AsyncConnection]]:
    """只连接显式指定的测试库；请求提交后由最外层事务统一回滚。"""
    settings = get_settings()
    test_database = os.getenv("MYSQL_TEST_DATABASE")
    if test_database is None:
        pytest.skip("未设置 MYSQL_TEST_DATABASE；真实 MySQL 集成测试需显式启用")
    if test_database != f"{settings.mysql_database}_test":
        raise RuntimeError("MYSQL_TEST_DATABASE 必须是学习库名称加 _test")

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
                """模拟真实请求的提交与异常回滚，但保留外层测试隔离。"""
                async with session_factory() as session:
                    try:
                        yield session
                        await session.commit()
                    except Exception:
                        await session.rollback()
                        raise

            app.dependency_overrides[get_session] = override_get_session
            try:
                transport = httpx.ASGITransport(app=app)
                async with httpx.AsyncClient(
                    transport=transport, base_url="http://testserver"
                ) as client:
                    yield client, connection
            finally:
                app.dependency_overrides.pop(get_session, None)
                # 保存点内的请求提交仍被外层事务包住，不会留下测试股票。
                await outer_transaction.rollback()
    finally:
        await engine.dispose()


async def _add_prices(
    connection: AsyncConnection,
    *,
    symbol: str,
    market: str,
    count: int,
    adjustment: str,
    source: str,
) -> int:
    """在测试事务中造已收盘日线，不调用真实外部行情网站。"""
    stock_result = await connection.execute(
        insert(Stock).values(symbol=symbol, name=symbol, market=market)
    )
    stock_id = stock_result.inserted_primary_key[0]
    currency = "CNY" if market == "CN" else "USD"
    start = date(2025, 1, 1)
    await connection.execute(
        insert(DailyPrice),
        [
            {
                "stock_id": stock_id,
                "trade_date": start + timedelta(days=index),
                "open_price": Decimal(100 + index),
                "high_price": Decimal(100 + index),
                "low_price": Decimal(100 + index),
                "close_price": Decimal(100 + index),
                "volume": 1000 + index,
                "currency": currency,
                "source": source,
                "adjustment": adjustment,
            }
            for index in range(count)
        ],
    )
    return stock_id


@pytest.mark.anyio
async def test_first_and_repeat_analysis_save_one_run_with_90_daily_results(
    analysis_client: tuple[httpx.AsyncClient, AsyncConnection],
) -> None:
    """首次返回 201；重算保留批次编号，前 34 天只有预热指标。"""
    client, connection = analysis_client
    stock_id = await _add_prices(
        connection,
        symbol="TESTANALYZE",
        market="US",
        count=90,
        adjustment="all",
        source="twelvedata",
    )

    first = await client.post(f"/stocks/{stock_id}/analysis-runs", json={"days": 90})
    repeated = await client.post(f"/stocks/{stock_id}/analysis-runs", json={"days": 90})

    assert first.status_code == 201
    assert repeated.status_code == 200
    body = first.json()
    assert repeated.json() == body
    assert body["stock_id"] == stock_id
    assert body["symbol"] == "TESTANALYZE"
    assert body["requested_days"] == body["saved"] == 90
    assert body["start_date"] == "2025-01-01"
    assert body["end_date"] == body["latest"]["trade_date"] == "2025-03-31"
    assert body["source"] == "twelvedata"
    assert body["adjustment"] == "all"
    assert body["rule_version"] == "v1"
    assert body["latest"]["close_price"] == "189.000000"
    assert isinstance(body["latest"]["trend_score"], int)
    assert body["latest"]["trend_label"]
    assert "趋势评分" in body["latest"]["summary"]

    # AsyncConnection 执行的是 Core 查询：明确选列，返回值才是所需的标量。
    run_ids = (
        (
            await connection.execute(
                select(AnalysisRun.id).where(AnalysisRun.stock_id == stock_id)
            )
        )
        .scalars()
        .all()
    )
    assert run_ids == [body["run_id"]]
    scores = (
        (
            await connection.execute(
                select(AnalysisResult.trend_score)
                .where(AnalysisResult.analysis_run_id == body["run_id"])
                .order_by(AnalysisResult.trade_date)
            )
        )
        .scalars()
        .all()
    )
    assert len(scores) == 90
    assert all(score is None for score in scores[:34])
    assert all(score is not None for score in scores[34:])


@pytest.mark.anyio
async def test_90_and_100_days_are_distinct_and_recalculation_replaces_old_rows(
    analysis_client: tuple[httpx.AsyncClient, AsyncConnection],
) -> None:
    """计算范围属于批次身份；修正历史行情后重算同一批次。"""
    client, connection = analysis_client
    stock_id = await _add_prices(
        connection,
        symbol="TESTRECALC",
        market="US",
        count=100,
        adjustment="all",
        source="twelvedata",
    )
    url = f"/stocks/{stock_id}/analysis-runs"
    run_90 = await client.post(url, json={"days": 90})
    run_100 = await client.post(url, json={"days": 100})
    assert run_90.status_code == run_100.status_code == 201
    assert run_90.json()["run_id"] != run_100.json()["run_id"]
    assert run_90.json()["start_date"] == "2025-01-11"
    assert run_100.json()["start_date"] == "2025-01-01"

    last_date = date(2025, 1, 1) + timedelta(days=99)
    await connection.execute(
        update(DailyPrice)
        .where(DailyPrice.stock_id == stock_id, DailyPrice.trade_date == last_date)
        .values(
            open_price=Decimal(300),
            high_price=Decimal(300),
            low_price=Decimal(300),
            close_price=Decimal(300),
        )
    )
    recalculated = await client.post(url, json={"days": 90})
    assert recalculated.status_code == 200
    assert recalculated.json()["run_id"] == run_90.json()["run_id"]
    assert recalculated.json()["latest"]["close_price"] == "300.000000"
    assert recalculated.json()["latest"]["ma5"] != run_90.json()["latest"]["ma5"]
    assert (
        await connection.execute(
            select(func.count())
            .select_from(AnalysisRun)
            .where(AnalysisRun.stock_id == stock_id)
        )
    ).scalar_one() == 2
    assert (
        await connection.execute(
            select(func.count())
            .select_from(AnalysisResult)
            .join(AnalysisRun)
            .where(AnalysisRun.stock_id == stock_id)
        )
    ).scalar_one() == 190


@pytest.mark.anyio
async def test_analysis_requires_full_requested_history_and_valid_parameters(
    analysis_client: tuple[httpx.AsyncClient, AsyncConnection],
) -> None:
    """少于指定条数不悄悄缩小范围，参数错误也不写入批次。"""
    client, connection = analysis_client
    stock_id = await _add_prices(
        connection,
        symbol="TESTSHORT",
        market="US",
        count=34,
        adjustment="all",
        source="twelvedata",
    )
    url = f"/stocks/{stock_id}/analysis-runs"
    insufficient = await client.post(url, json={"days": 35})
    invalid = await client.post(url, json={"days": 34})
    missing = await client.post("/stocks/99999999/analysis-runs", json={"days": 35})

    assert insufficient.status_code == 409
    assert insufficient.json() == {
        "code": 409,
        "message": "已存日线不足：需要35条，当前34条",
    }
    assert invalid.status_code == 422
    assert invalid.json()["errors"][0]["field"] == "body.days"
    assert missing.status_code == 404
    assert missing.json() == {"code": 404, "message": "股票不存在"}
    assert (
        await connection.execute(
            select(func.count())
            .select_from(AnalysisRun)
            .where(AnalysisRun.stock_id == stock_id)
        )
    ).scalar_one() == 0


@pytest.mark.anyio
async def test_analysis_accepts_cn_qfq_and_rejects_old_or_mixed_basis(
    analysis_client: tuple[httpx.AsyncClient, AsyncConnection],
) -> None:
    """A 股前复权能分析；未复权或混合来源不能进入 v1 结果。"""
    client, connection = analysis_client
    cn_id = await _add_prices(
        connection,
        symbol="600941.SH",
        market="CN",
        count=35,
        adjustment="qfq",
        source="tencent",
    )
    old_id = await _add_prices(
        connection,
        symbol="TESTOLD",
        market="US",
        count=35,
        adjustment="none",
        source="twelvedata",
    )
    valid = await client.post(f"/stocks/{cn_id}/analysis-runs", json={"days": 35})
    invalid = await client.post(f"/stocks/{old_id}/analysis-runs", json={"days": 35})
    assert valid.status_code == 201
    assert valid.json()["adjustment"] == "qfq"
    assert valid.json()["latest"]["trend_score"] is not None
    assert invalid.status_code == 409

    # 即使调整方式一样，混入不同来源仍会使这一轮数据口径不一致。
    await connection.execute(
        update(DailyPrice)
        .where(DailyPrice.stock_id == cn_id, DailyPrice.trade_date == date(2025, 1, 1))
        .values(source="other")
    )
    mixed = await client.post(f"/stocks/{cn_id}/analysis-runs", json={"days": 35})
    assert mixed.status_code == 409
    assert (
        await connection.execute(
            select(func.count())
            .select_from(AnalysisRun)
            .where(AnalysisRun.stock_id == old_id)
        )
    ).scalar_one() == 0


@pytest.mark.anyio
async def test_archived_stock_cannot_create_analysis_run(
    analysis_client: tuple[httpx.AsyncClient, AsyncConnection],
) -> None:
    """归档股票仍可查旧数据，但不能发起新的分析。"""
    client, connection = analysis_client
    stock_id = await _add_prices(
        connection,
        symbol="TESTARCHANA",
        market="US",
        count=35,
        adjustment="all",
        source="twelvedata",
    )
    await connection.execute(
        update(Stock)
        .where(Stock.id == stock_id)
        .values(archived_at=datetime(2025, 6, 1))
    )
    response = await client.post(f"/stocks/{stock_id}/analysis-runs", json={"days": 35})
    assert response.status_code == 409
    assert response.json() == {"code": 409, "message": "已归档股票不可发起新分析"}


@pytest.mark.anyio
async def test_analysis_relationships_require_explicit_loading_and_sort_results(
    analysis_client: tuple[httpx.AsyncClient, AsyncConnection],
) -> None:
    """真实异步 MySQL 中，未加载的关系会报错；显式预加载后可安全导航。"""
    client, connection = analysis_client
    stock_id = await _add_prices(
        connection,
        symbol="TESTREL",
        market="US",
        count=35,
        adjustment="all",
        source="twelvedata",
    )
    created = await client.post(f"/stocks/{stock_id}/analysis-runs", json={"days": 35})
    assert created.status_code == 201
    run_id = created.json()["run_id"]

    async with AsyncSession(
        connection, join_transaction_mode="create_savepoint"
    ) as session:
        run = (
            await session.execute(select(AnalysisRun).where(AnalysisRun.id == run_id))
        ).scalar_one()
        with pytest.raises(InvalidRequestError):
            _ = run.results

    async with AsyncSession(
        connection, join_transaction_mode="create_savepoint"
    ) as session:
        run = (
            await session.execute(
                select(AnalysisRun)
                .options(
                    selectinload(AnalysisRun.stock),
                    selectinload(AnalysisRun.results),
                )
                .where(AnalysisRun.id == run_id)
            )
        ).scalar_one()
        assert run.stock.symbol == "TESTREL"
        assert len(run.results) == 35
        assert [day.trade_date for day in run.results] == sorted(
            day.trade_date for day in run.results
        )
        assert run.results[-1].trend_score is not None


@pytest.mark.anyio
async def test_read_saved_analysis_run_returns_ordered_snapshot(
    analysis_client: tuple[httpx.AsyncClient, AsyncConnection],
) -> None:
    """详情接口返回已保存的 90 天结果，行情后来变化也不会暗中重算。"""
    client, connection = analysis_client
    stock_id = await _add_prices(
        connection,
        symbol="TESTREADRUN",
        market="US",
        count=90,
        adjustment="all",
        source="twelvedata",
    )
    created = await client.post(f"/stocks/{stock_id}/analysis-runs", json={"days": 90})
    assert created.status_code == 201
    run_id = created.json()["run_id"]

    # 改动原始日线后，查询结果仍应是分析时保存的快照。
    await connection.execute(
        update(DailyPrice)
        .where(
            DailyPrice.stock_id == stock_id, DailyPrice.trade_date == date(2025, 3, 31)
        )
        .values(close_price=Decimal(999))
    )
    response = await client.get(f"/stocks/{stock_id}/analysis-runs/{run_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["run_id"] == run_id
    assert body["stock_id"] == stock_id
    assert body["symbol"] == "TESTREADRUN"
    assert body["market"] == "US"
    assert body["requested_days"] == body["saved"] == len(body["items"]) == 90
    assert body["start_date"] == "2025-01-01"
    assert body["end_date"] == "2025-03-31"
    assert body["source"] == "twelvedata"
    assert body["adjustment"] == "all"
    assert body["rule_version"] == "v1"
    assert body["computed_at"].endswith("Z")
    assert [item["trade_date"] for item in body["items"]] == sorted(
        item["trade_date"] for item in body["items"]
    )
    assert body["items"][0]["trend_score"] is None
    assert body["items"][33]["trend_label"] is None
    assert body["items"][34]["trend_score"] is not None
    assert body["items"][-1]["close_price"] == "189.000000"
    assert body["items"][-1]["ma5"] == created.json()["latest"]["ma5"]
    assert body["items"][-1]["trend_score"] == created.json()["latest"]["trend_score"]
    assert (
        await connection.execute(
            select(func.count())
            .select_from(AnalysisResult)
            .where(AnalysisResult.analysis_run_id == run_id)
        )
    ).scalar_one() == 90


@pytest.mark.anyio
async def test_read_saved_analysis_run_allows_archive_and_hides_other_stocks_run(
    analysis_client: tuple[httpx.AsyncClient, AsyncConnection],
) -> None:
    """归档只阻止新分析；按错误股票编号查批次不能泄露别人的结果。"""
    client, connection = analysis_client
    stock_id = await _add_prices(
        connection,
        symbol="TESTREADARCH",
        market="CN",
        count=35,
        adjustment="qfq",
        source="tencent",
    )
    other_stock_id = await _add_prices(
        connection,
        symbol="TESTREADOTHER",
        market="US",
        count=35,
        adjustment="all",
        source="twelvedata",
    )
    created = await client.post(f"/stocks/{stock_id}/analysis-runs", json={"days": 35})
    assert created.status_code == 201
    run_id = created.json()["run_id"]
    await connection.execute(
        update(Stock)
        .where(Stock.id == stock_id)
        .values(archived_at=datetime(2025, 6, 1))
    )

    archived = await client.get(f"/stocks/{stock_id}/analysis-runs/{run_id}")
    wrong_stock = await client.get(f"/stocks/{other_stock_id}/analysis-runs/{run_id}")
    missing_run = await client.get(f"/stocks/{stock_id}/analysis-runs/99999999")
    invalid_stock = await client.get(f"/stocks/0/analysis-runs/{run_id}")
    invalid_run = await client.get(f"/stocks/{stock_id}/analysis-runs/0")

    assert archived.status_code == 200
    assert archived.json()["saved"] == 35
    assert wrong_stock.status_code == missing_run.status_code == 404
    assert wrong_stock.json() == {"code": 404, "message": "分析批次不存在"}
    assert missing_run.json() == wrong_stock.json()
    assert invalid_stock.status_code == invalid_run.status_code == 422
    assert invalid_stock.json()["errors"][0]["field"] == "path.stock_id"
    assert invalid_run.json()["errors"][0]["field"] == "path.run_id"


@pytest.mark.anyio
async def test_list_analysis_runs_paginates_in_latest_computed_order(
    analysis_client: tuple[httpx.AsyncClient, AsyncConnection],
) -> None:
    """列表只返回批次信息；先按计算时间倒序，相同时按编号倒序。"""
    client, connection = analysis_client
    stock_id = await _add_prices(
        connection,
        symbol="TESTRUNLIST",
        market="US",
        count=90,
        adjustment="all",
        source="twelvedata",
    )
    run_ids: dict[int, int] = {}
    for days in (90, 60, 35):
        created = await client.post(
            f"/stocks/{stock_id}/analysis-runs", json={"days": days}
        )
        assert created.status_code == 201
        run_ids[days] = created.json()["run_id"]

    # 固定排序用的时间，避免测试依赖机器运行速度和 MySQL 秒级时间精度。
    for days, computed_at in (
        (90, datetime(2025, 5, 2, 12)),
        (60, datetime(2025, 5, 1, 12)),
        (35, datetime(2025, 5, 1, 12)),
    ):
        await connection.execute(
            update(AnalysisRun)
            .where(AnalysisRun.id == run_ids[days])
            .values(computed_at=computed_at)
        )

    url = f"/stocks/{stock_id}/analysis-runs"
    first = await client.get(url, params={"page": 1, "page_size": 2})
    second = await client.get(url, params={"page": 2, "page_size": 2})
    third = await client.get(url, params={"page": 3, "page_size": 2})

    assert first.status_code == second.status_code == third.status_code == 200
    first_body, second_body, third_body = first.json(), second.json(), third.json()
    assert first_body["stock_id"] == stock_id
    assert first_body["symbol"] == "TESTRUNLIST"
    assert first_body["market"] == "US"
    assert first_body["total"] == second_body["total"] == third_body["total"] == 3
    assert first_body["page"] == 1 and first_body["page_size"] == 2
    assert [item["run_id"] for item in first_body["items"]] == [
        run_ids[90],
        run_ids[35],
    ]
    assert [item["run_id"] for item in second_body["items"]] == [run_ids[60]]
    assert third_body["items"] == []
    assert first_body["items"][0]["requested_days"] == 90
    assert first_body["items"][0]["end_date"] == "2025-03-31"
    assert first_body["items"][0]["source"] == "twelvedata"
    assert first_body["items"][0]["adjustment"] == "all"
    assert first_body["items"][0]["rule_version"] == "v1"
    assert first_body["items"][0]["computed_at"].endswith("Z")
    assert "results" not in first_body["items"][0]


@pytest.mark.anyio
async def test_list_analysis_runs_handles_empty_archive_missing_and_invalid_query(
    analysis_client: tuple[httpx.AsyncClient, AsyncConnection],
) -> None:
    """无批次与归档股票返回空列表；错误编号和分页参数按约定报错。"""
    client, connection = analysis_client
    stock_id = await _add_prices(
        connection,
        symbol="TESTRUNEMPTY",
        market="CN",
        count=35,
        adjustment="qfq",
        source="tencent",
    )
    url = f"/stocks/{stock_id}/analysis-runs"
    empty = await client.get(url)
    await connection.execute(
        update(Stock)
        .where(Stock.id == stock_id)
        .values(archived_at=datetime(2025, 6, 1))
    )
    archived = await client.get(url)
    missing = await client.get("/stocks/99999999/analysis-runs")
    invalid_stock = await client.get("/stocks/0/analysis-runs")
    invalid_page = await client.get(url, params={"page": 0})
    invalid_size = await client.get(url, params={"page_size": 101})

    assert empty.status_code == archived.status_code == 200
    assert (
        empty.json()
        == archived.json()
        == {
            "stock_id": stock_id,
            "symbol": "TESTRUNEMPTY",
            "market": "CN",
            "items": [],
            "total": 0,
            "page": 1,
            "page_size": 20,
        }
    )
    assert missing.status_code == 404
    assert missing.json() == {"code": 404, "message": "股票不存在"}
    assert invalid_stock.status_code == 422
    assert invalid_stock.json()["errors"][0]["field"] == "path.stock_id"
    assert invalid_page.status_code == invalid_size.status_code == 422
    assert invalid_page.json()["errors"][0]["field"] == "query.page"
    assert invalid_size.json()["errors"][0]["field"] == "query.page_size"
