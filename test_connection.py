#!/usr/bin/env python3
"""
실시간 데이터 연결 테스트 스크립트
"""
import requests
import pandas as pd
import time

def test_naver_finance(code="005930"):
    """네이버 금융 접속 테스트"""
    print(f"\n=== 네이버 금융 접속 테스트 (종목코드: {code}) ===")
    
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Referer": "https://finance.naver.com/",
    }
    
    try:
        url = "https://finance.naver.com/item/sise_day.naver"
        print(f"URL: {url}")
        print(f"Parameters: code={code}, page=1")
        
        response = requests.get(
            url,
            params={"code": code, "page": 1},
            headers=headers,
            timeout=10
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Content Length: {len(response.text)} bytes")
        
        if response.status_code == 200:
            # HTML 파싱 시도
            df_list = pd.read_html(response.text)
            print(f"✅ HTML 테이블 파싱 성공! 테이블 개수: {len(df_list)}")
            
            if df_list:
                df = df_list[0].dropna()
                print(f"데이터 행 수: {len(df)}")
                if not df.empty:
                    print("\n첫 5행:")
                    print(df.head())
                    return True
        else:
            print(f"❌ HTTP 오류: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ 오류 발생: {type(e).__name__}: {str(e)}")
        return False
    
    return False

def test_offline_csv_parsing():
    """CSV 파싱 테스트"""
    print("\n=== CSV 파싱 테스트 ===")
    
    # 샘플 OHLCV 데이터 생성
    import io
    sample_csv = """date,open,close,volume
2024-01-01,50000,51000,1000000
2024-01-02,51000,52000,1100000
2024-01-03,52000,51500,1200000
2024-01-04,51500,53000,1300000
2024-01-05,53000,54000,1400000
2024-01-06,54000,53500,1500000
2024-01-07,53500,55000,1600000
2024-01-08,55000,56000,1700000
2024-01-09,56000,55500,1800000
2024-01-10,55500,57000,1900000"""
    
    # 35일치 데이터 생성 (MACD 계산을 위해)
    for i in range(11, 40):
        price = 57000 + (i - 10) * 100
        sample_csv += f"\n2024-01-{i},{price},{price+1000},{2000000+i*10000}"
    
    print("샘플 CSV 데이터 생성 완료")
    print(f"총 행 수: {len(sample_csv.split(chr(10)))}")
    
    try:
        df = pd.read_csv(io.StringIO(sample_csv))
        print(f"✅ CSV 파싱 성공!")
        print(f"컬럼: {df.columns.tolist()}")
        print(f"행 수: {len(df)}")
        print(f"최신 종가: {df['close'].iloc[-1]}")
        return True
    except Exception as e:
        print(f"❌ 오류 발생: {type(e).__name__}: {str(e)}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("주식 스크리너 데이터 연결 테스트")
    print("=" * 60)
    
    # 테스트 1: 네이버 금융 접속
    test1_result = test_naver_finance("005930")  # 삼성전자
    
    # 테스트 2: CSV 파싱
    test2_result = test_offline_csv_parsing()
    
    # 결과 요약
    print("\n" + "=" * 60)
    print("테스트 결과 요약")
    print("=" * 60)
    print(f"1. 네이버 금융 실시간 조회: {'✅ 성공' if test1_result else '❌ 실패'}")
    print(f"2. 오프라인 CSV 파싱: {'✅ 성공' if test2_result else '❌ 실패'}")
    print("=" * 60)
    
    if not test1_result:
        print("\n⚠️ 실시간 조회가 실패했습니다.")
        print("   - Streamlit Cloud 환경에서는 네이버 금융 접속이 차단될 수 있습니다.")
        print("   - 오프라인 CSV 업로드 방식을 사용하세요.")
    else:
        print("\n✅ 실시간 조회가 정상 작동합니다!")
