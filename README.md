# Personal Budget Tracker

## Setup

### 1. Google Sheets 준비

1. [Google Cloud Console](https://console.cloud.google.com)에서 프로젝트 생성
2. Google Sheets API 활성화
3. Service Account 생성 → JSON 키 다운로드 → `credentials.json`으로 저장
4. Google Sheets에서 새 스프레드시트 생성
5. 스프레드시트 URL의 ID 복사 (`.../spreadsheets/d/<ID>/edit`)
6. 스프레드시트 공유 → service account 이메일에 편집자 권한 부여

### 2. 환경 변수 설정

```bash
export SPREADSHEET_ID="your-spreadsheet-id"
export GOOGLE_CREDENTIALS="credentials.json"  # default
```

### 3. 의존성 설치

```bash
pip install -r requirements.txt
```

## 사용법

```bash
# 국민카드 CSV 가져오기
python import_cmd.py --files kb_card_may.csv

# 여러 파일 동시에
python import_cmd.py --files kb_card.csv naver_pay.csv kakao_pay.csv

# 소스 직접 지정
python import_cmd.py --files statement.csv --source kb
```

처음 실행하면 알 수 없는 가맹점마다 카테고리를 입력하라는 프롬프트가 나타납니다.
같은 가맹점은 다음 실행부터 자동으로 분류됩니다.

## CSV 파일 형식

각 카드사/앱 앱에서 내보낸 CSV를 그대로 사용합니다.
실제 내보낸 CSV의 컬럼명이 다르면 각 파서 파일 상단의 `*_COL` 상수를 수정하세요.

- `parsers/kb_card.py` → `DATE_COL`, `MERCHANT_COL`, `AMOUNT_COL`
- `parsers/naver_pay.py` → `DATE_COL`, `MERCHANT_COL`, `AMOUNT_COL`, `STATUS_COL`
- `parsers/kakao_pay.py` → `DATE_COL`, `MERCHANT_COL`, `AMOUNT_COL`, `TYPE_COL`
