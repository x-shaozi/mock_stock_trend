"""检查根路径返回可用的 API 入口信息。"""

from fastapi.testclient import TestClient

from app.main import app


def test_home_returns_service_name_and_entry_links() -> None:
    """打开根路径应得到服务信息，而不再收到资源不存在。"""
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "name": "模拟股票趋势 API",
        "docs": "/docs",
        "health": "/health",
    }
