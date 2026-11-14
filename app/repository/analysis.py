"""保存一次分析批次及其逐日结果；数据库会话只由仓储持有。"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.analysis_result import AnalysisResult
from app.models.analysis_run import AnalysisRun


@dataclass(frozen=True, slots=True)
class AnalysisDay:
    """业务层算好的一天结果；仓储把它映射为数据库中的一行。"""

    trade_date: date
    close_price: Decimal
    ma5: Decimal | None
    ma20: Decimal | None
    rsi14: Decimal | None
    macd: Decimal | None
    trend_score: int | None
    trend_label: str | None
    summary: str | None


class AnalysisRepository:
    """查询或保存分析批次；数据库会话只在这一层使用。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def count_runs(self, stock_id: int) -> int:
        """统计这只股票保存过多少轮分析，供列表显示总数。"""
        result = await self._session.execute(
            select(func.count())
            .select_from(AnalysisRun)
            .where(AnalysisRun.stock_id == stock_id)
        )
        return result.scalar_one()

    async def list_run_page(
        self, *, stock_id: int, offset: int, limit: int
    ) -> list[AnalysisRun]:
        """只取一页批次；不加载逐日结果，避免列表一次读取大量数据。"""
        # 计算时间相同的批次再按自增编号排序，让翻页有稳定顺序。
        result = await self._session.execute(
            select(AnalysisRun)
            .where(AnalysisRun.stock_id == stock_id)
            .order_by(AnalysisRun.computed_at.desc(), AnalysisRun.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_run_for_stock(
        self, *, stock_id: int, run_id: int
    ) -> AnalysisRun | None:
        """按股票和批次编号读取已保存结果，并明确加载两组 ORM 关系。"""
        # 模型把关系设为 lazy="raise"，防止在访问 run.stock 或 run.results 时
        # 偷偷发出数据库查询。这里预先加载，路由组装响应时就不再做 I/O。
        result = await self._session.execute(
            select(AnalysisRun)
            .options(
                selectinload(AnalysisRun.stock),
                selectinload(AnalysisRun.results),
            )
            .where(AnalysisRun.id == run_id, AnalysisRun.stock_id == stock_id)
        )
        return result.scalar_one_or_none()

    async def save_run(
        self,
        *,
        stock_id: int,
        requested_days: int,
        source: str,
        adjustment: str,
        rule_version: str,
        days: list[AnalysisDay],
    ) -> tuple[AnalysisRun, bool]:
        """首次创建批次；同一请求条件重算时，原批次编号保持不变。"""
        # 一次分析至少有 35 天。调用方已验证这一点，所以首尾日期都存在。
        # 股票行已由业务层锁住：同一股票的采集和分析不会并发修改输入。
        start_date, end_date = days[0].trade_date, days[-1].trade_date
        result = await self._session.execute(
            select(AnalysisRun).where(
                AnalysisRun.stock_id == stock_id,
                AnalysisRun.requested_days == requested_days,
                AnalysisRun.end_date == end_date,
                AnalysisRun.rule_version == rule_version,
            )
        )
        run = result.scalar_one_or_none()
        created = run is None
        if run is None:
            run = AnalysisRun(
                stock_id=stock_id,
                requested_days=requested_days,
                start_date=start_date,
                end_date=end_date,
                source=source,
                adjustment=adjustment,
                rule_version=rule_version,
            )
            self._session.add(run)
            # 先发送 INSERT，取得数据库生成的 run.id，供每日结果作外键。
            await self._session.flush()
        else:
            # 补录旧日线后，即使结束日期没变，实际起点也可能改变。
            # 清掉这轮旧结果，再完整写入本次计算所得的日期集合。
            # 删除与插入都在同一事务；任何一步失败会一起回滚。
            run.start_date = start_date
            run.source = source
            run.adjustment = adjustment
            run.computed_at = func.utc_timestamp()
            await self._session.execute(
                delete(AnalysisResult).where(AnalysisResult.analysis_run_id == run.id)
            )

        self._session.add_all(
            AnalysisResult(
                analysis_run_id=run.id,
                trade_date=day.trade_date,
                close_price=day.close_price,
                ma5=day.ma5,
                ma20=day.ma20,
                rsi14=day.rsi14,
                macd=day.macd,
                trend_score=day.trend_score,
                trend_label=day.trend_label,
                summary=day.summary,
            )
            for day in days
        )
        # 在路由生成成功响应前执行 SQL，及早发现唯一约束或字段问题。
        await self._session.flush()
        return run, created
