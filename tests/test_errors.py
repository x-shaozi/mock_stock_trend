from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from app.core.exceptions import register_exception_handlers
from app.main import app


def test_unknown_path_uses_api_response() -> None:
    with TestClient(app) as client:
        response = client.get("/missing")

    assert response.status_code == 404
    assert response.json() == {"code": 404, "message": "资源不存在"}


def test_validation_error_omits_input_value() -> None:
    test_app = FastAPI()
    register_exception_handlers(test_app)

    class Item(BaseModel):
        quantity: int = Field(ge=1)

    @test_app.post("/items")
    async def create_item(item: Item) -> dict[str, int]:
        return {"quantity": item.quantity}

    with TestClient(test_app) as client:
        response = client.post("/items", json={"quantity": -1})

    assert response.status_code == 422
    assert response.json()["code"] == 422
    assert response.json()["message"] == "请求参数不合法"
    assert response.json()["errors"][0]["field"] == "body.quantity"
    assert "input" not in response.json()["errors"][0]


def test_internal_error_hides_exception_details() -> None:
    test_app = FastAPI()
    register_exception_handlers(test_app)

    @test_app.get("/fail")
    async def fail() -> None:
        raise RuntimeError("内部敏感信息")

    with TestClient(test_app, raise_server_exceptions=False) as client:
        response = client.get("/fail")

    assert response.status_code == 500
    assert response.json() == {"code": 500, "message": "服务器内部错误"}
