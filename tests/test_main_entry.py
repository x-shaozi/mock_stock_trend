from pathlib import Path
from runpy import run_path
from unittest.mock import patch


def test_running_main_module_starts_development_server() -> None:
    main_file = Path(__file__).resolve().parents[1] / "app" / "main.py"

    with patch("uvicorn.run") as run_server:
        run_path(str(main_file), run_name="__main__")

    run_server.assert_called_once_with(
        "app.main:app", host="127.0.0.1", port=18000, reload=True
    )
