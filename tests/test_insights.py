from datetime import date
from unittest.mock import MagicMock, patch
import json

from insights import build_insight_context, build_insight_rows, build_prompt, generate_openai_insights
from models import Transaction


def test_builds_significant_category_and_merchant_context():
    txns = [
        Transaction(date=date(2026, 5, 1), amount=42000, merchant="배달의민족", category="식비", source="kb"),
        Transaction(date=date(2026, 5, 8), amount=38000, merchant="배달의민족", category="식비", source="kb"),
        Transaction(date=date(2026, 5, 10), amount=12000, merchant="동네식당", category="식비", source="kb"),
        Transaction(date=date(2026, 4, 3), amount=15000, merchant="배달의민족", category="식비", source="kb"),
        Transaction(date=date(2026, 4, 9), amount=10000, merchant="동네식당", category="식비", source="kb"),
        Transaction(date=date(2026, 5, 2), amount=20000, merchant="넷플릭스", category="구독", source="kb"),
        Transaction(date=date(2026, 4, 2), amount=39900, merchant="넷플릭스", category="구독", source="kb"),
    ]

    context = build_insight_context(txns)

    assert context["latest_label"] == "2026년 5월"
    assert context["previous_label"] == "2026년 4월"
    food = context["category_changes"][0]
    assert food["category"] == "식비"
    assert food["delta"] == 67000
    assert food["latest_total"] == 92000
    assert food["previous_total"] == 25000
    assert food["merchant_drivers"][0]["merchant"] == "배달의민족"
    assert food["merchant_drivers"][0]["delta"] == 65000


def test_prompt_rejects_bland_advice():
    context = {
        "latest_label": "2026년 5월",
        "previous_label": "2026년 4월",
        "latest_total": 100000,
        "previous_total": 50000,
        "total_delta": 50000,
        "category_changes": [],
    }

    prompt = build_prompt(context)

    assert "외식을 줄이세요" in prompt
    assert "구체적인" in prompt


def test_build_insight_rows_uses_llm_output_when_available():
    def fake_llm(prompt):
        assert "2026년 5월" in prompt
        return "- 식비 증가분 대부분이 배달의민족 2건에서 나왔습니다."

    txns = [
        Transaction(date=date(2026, 5, 1), amount=60000, merchant="배달의민족", category="식비", source="kb"),
        Transaction(date=date(2026, 4, 1), amount=10000, merchant="배달의민족", category="식비", source="kb"),
    ]

    rows = build_insight_rows(txns, llm=fake_llm)

    assert rows == [
        ["AI 월간 인사이트", "", "", ""],
        ["- 식비 증가분 대부분이 배달의민족 2건에서 나왔습니다.", "", "", ""],
        ["", "", "", ""],
    ]


@patch.dict("os.environ", {"OPENAI_API_KEY": "key", "OPENAI_WEB_SEARCH": "true"}, clear=True)
@patch("insights.urllib.request.urlopen")
def test_generate_openai_insights_enables_web_search_when_configured(mock_urlopen):
    response = MagicMock()
    response.__enter__.return_value.read.return_value = json.dumps({
        "output_text": "- 배달비 구독 옵션을 확인해 볼 만합니다."
    }).encode("utf-8")
    mock_urlopen.return_value = response

    result = generate_openai_insights("prompt")

    request = mock_urlopen.call_args[0][0]
    payload = json.loads(request.data.decode("utf-8"))
    assert payload["tools"] == [{"type": "web_search"}]
    assert "웹 검색" in payload["input"]
    assert result == "- 배달비 구독 옵션을 확인해 볼 만합니다."


@patch.dict("os.environ", {"OPENAI_API_KEY": "key"}, clear=True)
@patch("insights.urllib.request.urlopen")
def test_generate_openai_insights_skips_web_search_by_default(mock_urlopen):
    response = MagicMock()
    response.__enter__.return_value.read.return_value = json.dumps({
        "output_text": "- 식비 증가분 대부분이 특정 가맹점에서 나왔습니다."
    }).encode("utf-8")
    mock_urlopen.return_value = response

    generate_openai_insights("prompt")

    request = mock_urlopen.call_args[0][0]
    payload = json.loads(request.data.decode("utf-8"))
    assert "tools" not in payload
