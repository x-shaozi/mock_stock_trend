import asyncio

import httpx


async def main() -> None:
    async with httpx.AsyncClient(timeout=15) as client:
        us_response, cn_response = await asyncio.gather(
            client.get(
                "https://api.twelvedata.com/time_series",
                params={
                    "symbol": "AAPL",
                    "interval": "1day",
                    "outputsize": 5,
                    "adjust": "none",
                    "apikey": "demo",
                },
            ),
            client.get(
                "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get",
                params={"param": "sh688385,day,,,5,"},
            ),
        )

    us_response.raise_for_status()
    cn_response.raise_for_status()

    us_data = us_response.json()
    print("美股 AAPL：", us_data["values"][0])

    cn_data = cn_response.json()
    cn_rows = cn_data["data"]["sh688385"]["day"]
    date, open_price, close_price, high_price, low_price, volume = cn_rows[-1][:6]
    print(
        "A 股 688385：",
        {
            "日期": date,
            "开盘": open_price,
            "最高": high_price,
            "最低": low_price,
            "收盘": close_price,
            "成交量": volume,
        },
    )


asyncio.run(main())
