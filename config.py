import os
from pathlib import Path

ENV_FILE = Path(".env")


def load_dotenv(path: Path = ENV_FILE) -> None:
    if not path.exists():
        return

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line.removeprefix("export ").strip()
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def validate_config() -> None:
    if not SPREADSHEET_ID:
        raise SystemExit(
            "SPREADSHEET_ID가 설정되지 않았습니다. .env에 SPREADSHEET_ID를 추가하거나 "
            "`export SPREADSHEET_ID=\"...\"` 후 다시 실행하세요."
        )
    if not Path(CREDENTIALS_FILE).exists():
        raise SystemExit(
            f"Google credentials 파일을 찾을 수 없습니다: {CREDENTIALS_FILE}. "
            ".env의 GOOGLE_CREDENTIALS 값을 확인하거나 credentials.json을 프로젝트 루트에 두세요."
        )


load_dotenv()

SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID", "")
CREDENTIALS_FILE = os.environ.get("GOOGLE_CREDENTIALS", "credentials.json")
