# 🔧 실시간 조회 및 데이터 연결 문제 해결 가이드

## 📊 수정 사항

### 개선된 기능
1. **상세한 디버깅 로그 추가**
   - 실시간 데이터 조회 시 성공/실패 상태를 콘솔에 출력
   - 오프라인 데이터 사용 시 어떤 데이터를 사용하는지 명확히 표시
   - CSV 파싱 시 컬럼 매핑 정보와 오류 원인 출력

2. **에러 처리 강화**
   - `get_stock_data_live()`: 네이버 금융 접속 실패 시 구체적인 에러 메시지 출력
   - `get_stock_data()`: 오프라인/라이브 데이터 흐름을 명확히 로깅
   - `parse_ohlcv_csv()`: CSV 파싱 각 단계에서 상세 정보 출력

3. **코드 품질 개선**
   - Windows 줄바꿈 문자(`\r\n`)를 Unix 형식(`\n`)으로 통일
   - 일관된 코드 포맷팅

## 🧪 테스트 결과

테스트 스크립트(`test_connection.py`) 실행 결과:
```
✅ 네이버 금융 실시간 조회: 성공
✅ 오프라인 CSV 파싱: 성공
```

**실시간 데이터 조회가 정상 작동합니다!**

## 🚀 사용 방법

### 방법 1: 실시간 조회 (기본)

앱이 자동으로 네이버 금융에서 실시간 데이터를 가져옵니다.

1. 기업명 검색 (예: 삼성전자)
2. 종목 선택
3. "분석 시작" 버튼 클릭
4. 자동으로 실시간 데이터 조회 및 분석

### 방법 2: 오프라인 CSV 업로드

실시간 조회가 안 될 경우 (Streamlit Cloud 등):

1. OHLCV 데이터를 CSV 파일로 준비
   ```csv
   date,open,close,volume
   2024-01-01,50000,51000,1000000
   2024-01-02,51000,52000,1100000
   ...
   ```

2. 필수 컬럼:
   - `close` 또는 `종가` (필수)
   - `volume` 또는 `거래량` (필수)
   - `open` 또는 `시가` (선택)
   - `date` 또는 `날짜` (선택)

3. 최소 35행 이상의 데이터 필요 (MACD 계산을 위해)

4. 앱에서 CSV 업로드:
   - Tab3 (개별 종목 분석): 특정 종목 OHLCV 업로드
   - Tab2 (관심종목 스크리닝): 여러 종목 OHLCV 일괄 업로드

## 🔍 디버깅 정보 확인

앱 실행 중 콘솔에서 다음과 같은 로그를 확인할 수 있습니다:

```
[INFO] Attempting live data fetch: 005930
[SUCCESS] Live data fetch successful: 005930
```

또는

```
[INFO] Using offline data: 005930
```

오류 발생 시:
```
[ERROR] Live data fetch failed (005930): ConnectionError...
[WARNING] Live data fetch failed: 005930
```

CSV 업로드 시:
```
[INFO] Parsing OHLCV CSV: samsung_005930.csv
[INFO] Columns found: ['date', 'open', 'close', 'volume']
[INFO] Mapped columns - close: close, volume: volume, open: open, date: date
[SUCCESS] OHLCV parsed successfully. Rows: 60, Current: 162200.0
```

## 🛠️ 문제 해결

### 실시간 조회가 안 되는 경우

**증상**: "⚠️ 라이브 시세를 못 가져왔습니다" 메시지

**원인**:
- Streamlit Cloud에서 네이버 금융 접속이 차단됨
- 네트워크 오류
- 종목 코드가 잘못됨

**해결책**:
1. 콘솔 로그를 확인하여 정확한 오류 원인 파악
2. 오프라인 CSV 업로드 방식 사용
3. 종목 코드 확인 (6자리 숫자, 예: 005930)

### CSV 업로드가 안 되는 경우

**증상**: "❌ OHLCV CSV 형식이 올바르지 않습니다" 메시지

**원인**:
- 필수 컬럼(`close`, `volume`) 누락
- 데이터 행이 35개 미만
- CSV 인코딩 문제

**해결책**:
1. CSV 컬럼명 확인:
   - 영문: `close`, `volume`, `open`, `date`
   - 한글: `종가`, `거래량`, `시가`, `날짜`
2. 최소 35행 이상의 데이터 준비
3. UTF-8 인코딩으로 저장
4. 콘솔 로그에서 파싱 과정 확인

### 데이터 연결 테스트

터미널에서 테스트 스크립트 실행:

```bash
cd /home/user/webapp
python test_connection.py
```

## 📝 추가 개선 사항

향후 추가할 수 있는 기능:
- [ ] Streamlit UI에서도 디버깅 로그 표시 (선택적)
- [ ] 다른 데이터 소스 추가 (Yahoo Finance, Alpha Vantage 등)
- [ ] CSV 업로드 시 자동 포맷 감지 및 변환
- [ ] 데이터 캐싱 개선 (더 긴 TTL 또는 영구 저장)

## 🌐 앱 접속

현재 실행 중인 앱:
- URL: https://8501-ikvlp95n72qa1xmqucdb0-02b9cc79.sandbox.novita.ai

## 📞 문제 보고

문제가 계속되면 다음 정보와 함께 보고해주세요:
1. 정확한 에러 메시지
2. 콘솔 로그 (특히 `[ERROR]`로 시작하는 줄)
3. 사용한 종목 코드
4. CSV 파일 샘플 (업로드 방식 사용 시)
