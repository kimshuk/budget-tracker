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

`expense/` 폴더에 내보낸 파일을 넣고 실행합니다.

```bash
# expense/ 폴더의 모든 파일 자동 인식
python import_cmd.py

# 파일 직접 지정
python import_cmd.py --files kb_card_may.xls kb_bank_may.xls

# 소스 직접 지정
python import_cmd.py --files statement.xls --source kb
```

## 지원 파일 형식

국민카드·국민은행 앱에서 내보낸 `.xls` 파일을 그대로 사용합니다.

| 소스 | 파일명 패턴 | 비고 |
|------|------------|------|
| 국민카드 | `*카드*.xls` | 국내이용금액=0 (해외결제) 자동 제외 |
| 국민은행 계좌 | `*은행*.xls` / `*bank*.xls` | 출금 내역만 가져옴, KB카드 자동이체 제외 |

파서 파일 상단의 `*_COL` 상수를 수정하면 컬럼명을 커스텀할 수 있습니다.

- `parsers/kb_card.py` → `DATE_COL`, `MERCHANT_COL`, `AMOUNT_COL`
- `parsers/kb_bank.py` → `DATE_COL`, `MERCHANT_COL`, `AMOUNT_COL`

## 카테고리 분류 방식

CLI 프롬프트 없이 Google Sheets에서 직접 관리합니다.

1. **첫 실행 시** `categories` 시트에 기본 카테고리 목록이 자동 생성됩니다  
   (식비, 카페, 쇼핑, 교통, 의료, 생활비, 여가/문화, 구독, 기타)

2. **미등록 가맹점**은 `merchant_categories` 시트에 빈 카테고리로 추가되고,  
   해당 거래는 transactions 시트에 `미분류`로 기록됩니다.

3. **Sheets에서 카테고리 입력**: `merchant_categories` 시트의 B열 드롭다운에서  
   카테고리를 선택하거나 직접 입력합니다.

4. **다음 실행 시** `미분류` 거래가 자동으로 업데이트됩니다.

## 대시보드

매 실행마다 `dashboard` 시트가 자동 재생성됩니다.  
월별 카테고리 합계를 보여주며, 각 카테고리 행을 펼치면 세부 거래 내역을 확인할 수 있습니다.  
카테고리 그룹은 기본적으로 접힌 상태로 표시됩니다.
