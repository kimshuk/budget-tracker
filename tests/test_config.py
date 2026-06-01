import os

from config import load_dotenv


def test_load_dotenv_reads_export_assignments(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "export SPREADSHEET_ID=sheet-id\n"
        "export GOOGLE_CREDENTIALS=creds.json\n",
        encoding="utf-8",
    )

    old_spreadsheet_id = os.environ.pop("SPREADSHEET_ID", None)
    old_google_credentials = os.environ.pop("GOOGLE_CREDENTIALS", None)
    try:
        load_dotenv(env_file)

        assert os.environ["SPREADSHEET_ID"] == "sheet-id"
        assert os.environ["GOOGLE_CREDENTIALS"] == "creds.json"
    finally:
        if old_spreadsheet_id is not None:
            os.environ["SPREADSHEET_ID"] = old_spreadsheet_id
        else:
            os.environ.pop("SPREADSHEET_ID", None)
        if old_google_credentials is not None:
            os.environ["GOOGLE_CREDENTIALS"] = old_google_credentials
        else:
            os.environ.pop("GOOGLE_CREDENTIALS", None)


def test_load_dotenv_does_not_override_existing_environment(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("SPREADSHEET_ID=from-file\n", encoding="utf-8")

    old_spreadsheet_id = os.environ.get("SPREADSHEET_ID")
    os.environ["SPREADSHEET_ID"] = "from-env"
    try:
        load_dotenv(env_file)

        assert os.environ["SPREADSHEET_ID"] == "from-env"
    finally:
        if old_spreadsheet_id is not None:
            os.environ["SPREADSHEET_ID"] = old_spreadsheet_id
        else:
            os.environ.pop("SPREADSHEET_ID", None)
