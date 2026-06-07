import json
import os
import urllib.error
import urllib.request
from collections import defaultdict
from collections.abc import Callable
from models import Transaction

MIN_CATEGORY_DELTA = 30000
MIN_CATEGORY_DELTA_RATIO = 0.25
MIN_MERCHANT_DELTA = 15000
MAX_CATEGORY_CHANGES = 5
MAX_MERCHANT_DRIVERS = 3


def build_insight_rows(
    transactions: list[Transaction],
    llm: Callable[[str], str] | None = None,
) -> list[list]:
    context = build_insight_context(transactions)
    if not context:
        return []

    prompt = build_prompt(context)
    generator = llm or generate_openai_insights
    text = generator(prompt) or fallback_insights(context)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        lines = [fallback_insights(context)]

    return [["AI 월간 인사이트", "", "", ""]] + [[line, "", "", ""] for line in lines[:5]] + [["", "", "", ""]]


def build_insight_context(transactions: list[Transaction]) -> dict | None:
    by_month: dict[tuple[int, int], list[Transaction]] = defaultdict(list)
    for txn in transactions:
        by_month[(txn.date.year, txn.date.month)].append(txn)

    recent_months = sorted(by_month.keys(), reverse=True)[:2]
    if len(recent_months) < 2:
        return None

    latest, previous = recent_months
    latest_txns = by_month[latest]
    previous_txns = by_month[previous]
    latest_category_totals = _totals_by(latest_txns, "category")
    previous_category_totals = _totals_by(previous_txns, "category")

    changes = []
    for category in sorted(set(latest_category_totals) | set(previous_category_totals)):
        latest_total = latest_category_totals.get(category, 0)
        previous_total = previous_category_totals.get(category, 0)
        delta = latest_total - previous_total
        ratio = None if previous_total == 0 else delta / previous_total
        if not _is_significant(delta, ratio):
            continue

        changes.append({
            "category": category,
            "latest_total": latest_total,
            "previous_total": previous_total,
            "delta": delta,
            "delta_ratio": ratio,
            "merchant_drivers": _merchant_drivers(category, latest_txns, previous_txns, delta),
        })

    changes.sort(key=lambda change: abs(change["delta"]), reverse=True)

    return {
        "latest_label": _month_label(latest),
        "previous_label": _month_label(previous),
        "latest_total": sum(txn.amount for txn in latest_txns),
        "previous_total": sum(txn.amount for txn in previous_txns),
        "total_delta": sum(txn.amount for txn in latest_txns) - sum(txn.amount for txn in previous_txns),
        "category_changes": changes[:MAX_CATEGORY_CHANGES],
    }


def build_prompt(context: dict) -> str:
    return (
        "최근 두 달의 개인 지출 변화를 분석해 주세요.\n"
        "반드시 아래 JSON 사실만 근거로 삼고, 금액/월/카테고리/가맹점을 구체적으로 언급하세요.\n"
        "출력은 한국어 bullet 3-5개만 작성하세요.\n"
        "너무 뻔하거나 일반적인 조언은 금지합니다. 예: '외식을 줄이세요', '쇼핑을 줄이세요', '예산을 세우세요'.\n"
        "팁은 해결 가능한 구체적인 패턴이 있을 때만 제안하세요.\n"
        "두드러진 변화가 없으면 한 줄로 '- 특별히 두드러진 변화가 없습니다.'라고 답하세요.\n\n"
        f"{json.dumps(context, ensure_ascii=False, indent=2)}"
    )


def generate_openai_insights(prompt: str) -> str:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return ""

    payload = {
        "model": os.environ.get("OPENAI_MODEL", "gpt-5"),
        "input": prompt,
        "max_output_tokens": 600,
    }
    if _web_search_enabled():
        payload["tools"] = [{"type": "web_search"}]
        payload["input"] += (
            "\n\n웹 검색을 사용할 수 있습니다. 현재 가격, 멤버십, 대체 서비스, 정책처럼 "
            "최신 정보가 팁의 품질을 높일 때만 검색하세요. 검색 결과를 사용했다면 "
            "출처가 드러나도록 간단히 언급하세요."
        )
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return ""

    return _extract_response_text(data)


def fallback_insights(context: dict) -> str:
    changes = context.get("category_changes", [])
    if not changes:
        return "- 특별히 두드러진 변화가 없습니다."

    lines = []
    for change in changes[:3]:
        direction = "늘었습니다" if change["delta"] > 0 else "줄었습니다"
        line = (
            f"- {context['latest_label']} {change['category']} 지출이 "
            f"{context['previous_label']}보다 {_won(abs(change['delta']))} {direction}."
        )
        if change["delta"] > 0 and change["merchant_drivers"]:
            driver = change["merchant_drivers"][0]
            line += (
                f" 증가분의 대부분은 {driver['merchant']}에서 나온 "
                f"{_won(driver['delta'])} 변화입니다."
            )
        lines.append(line)
    return "\n".join(lines)


def _merchant_drivers(
    category: str,
    latest_txns: list[Transaction],
    previous_txns: list[Transaction],
    category_delta: int,
) -> list[dict]:
    if category_delta <= 0:
        return []

    latest = _totals_by([txn for txn in latest_txns if txn.category == category], "merchant")
    previous = _totals_by([txn for txn in previous_txns if txn.category == category], "merchant")
    counts = _counts_by([txn for txn in latest_txns if txn.category == category], "merchant")
    drivers = []
    for merchant in sorted(set(latest) | set(previous)):
        delta = latest.get(merchant, 0) - previous.get(merchant, 0)
        if delta < MIN_MERCHANT_DELTA:
            continue
        drivers.append({
            "merchant": merchant,
            "latest_total": latest.get(merchant, 0),
            "previous_total": previous.get(merchant, 0),
            "delta": delta,
            "latest_count": counts.get(merchant, 0),
        })
    drivers.sort(key=lambda driver: driver["delta"], reverse=True)
    return drivers[:MAX_MERCHANT_DRIVERS]


def _totals_by(transactions: list[Transaction], attr: str) -> dict[str, int]:
    totals: dict[str, int] = defaultdict(int)
    for txn in transactions:
        totals[getattr(txn, attr)] += txn.amount
    return dict(totals)


def _counts_by(transactions: list[Transaction], attr: str) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for txn in transactions:
        counts[getattr(txn, attr)] += 1
    return dict(counts)


def _is_significant(delta: int, ratio: float | None) -> bool:
    if abs(delta) < MIN_CATEGORY_DELTA:
        return False
    return ratio is None or abs(ratio) >= MIN_CATEGORY_DELTA_RATIO


def _extract_response_text(data: dict) -> str:
    if data.get("output_text"):
        return data["output_text"].strip()

    chunks = []
    for item in data.get("output", []):
        for content in item.get("content", []):
            text = content.get("text")
            if text:
                chunks.append(text)
    return "\n".join(chunks).strip()


def _web_search_enabled() -> bool:
    value = os.environ.get("OPENAI_WEB_SEARCH", "")
    return value.lower() in {"1", "true", "yes", "on"}


def _month_label(month: tuple[int, int]) -> str:
    return f"{month[0]}년 {month[1]}월"


def _won(amount: int) -> str:
    return f"₩{amount:,}"
