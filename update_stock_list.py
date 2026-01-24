import requests
import pandas as pd
from io import BytesIO
import time
import sys

def method1_krx_otp():
    """방법 1: KRX OTP 방식 (기본)"""
    print("\n[방법 1] KRX OTP 방식 시도 중...")
    
    try:
        session = requests.Session()
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9',
            'Referer': 'http://data.krx.co.kr/contents/MDC/MDI/mdiLoader/index.cmd?menuId=MDC0201',
        }
        
        # 메인 페이지 접속
        session.get('http://data.krx.co.kr/contents/MDC/MDI/mdiLoader/index.cmd?menuId=MDC0201', 
                   headers=headers, timeout=30)
        time.sleep(1)
        
        # OTP 생성
        gen_otp_url = 'http://data.krx.co.kr/comm/fileDn/GenerateOTP/generate.cmd'
        otp_data = {
            'mktId': 'ALL',
            'share': '1',
            'csvxls_isNo': 'false',
            'name': 'fileDown',
            'url': 'dbms/MDC/STAT/standard/MDCSTAT01901'
        }
        
        otp_response = session.post(gen_otp_url, data=otp_data, headers=headers, timeout=30)
        otp = otp_response.text.strip()
        
        if not otp or len(otp) < 10 or 'LOGOUT' in otp or 'error' in otp.lower():
            raise Exception(f"OTP 생성 실패: {otp[:50]}")
        
        print(f"✅ OTP 생성 성공: {otp[:30]}...")
        time.sleep(1)
        
        # CSV 다운로드
        down_url = 'http://data.krx.co.kr/comm/fileDn/download_csv/download.cmd'
        down_response = session.post(down_url, data={'code': otp}, headers=headers, timeout=60)
        
        if len(down_response.content) < 1000:
            raise Exception(f"다운로드 데이터 부족: {len(down_response.content)} bytes")
        
        # CSV 파싱
        df = pd.read_csv(BytesIO(down_response.content), encoding='EUC-KR')
        print(f"✅ 방법 1 성공! {len(df)}개 종목 다운로드")
        return df
        
    except Exception as e:
        print(f"❌ 방법 1 실패: {e}")
        return None


def method2_krx_json():
    """방법 2: KRX JSON API 방식"""
    print("\n[방법 2] KRX JSON API 방식 시도 중...")
    
    try:
        session = requests.Session()
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': 'http://data.krx.co.kr/contents/MDC/MDI/mdiLoader/index.cmd?menuId=MDC0201'
        }
        
        # 메인 페이지
        session.get('http://data.krx.co.kr/contents/MDC/MDI/mdiLoader/index.cmd?menuId=MDC0201',
                   headers=headers, timeout=30)
        time.sleep(1)
        
        # JSON 데이터 요청
        json_url = 'http://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd'
        json_data = {
            'bld': 'dbms/MDC/STAT/standard/MDCSTAT01901',
            'locale': 'ko_KR',
            'mktId': 'ALL',
            'share': '1',
            'csvxls_isNo': 'false'
        }
        
        json_response = session.post(json_url, data=json_data, headers=headers, timeout=60)
        json_result = json_response.json()
        
        if 'OutBlock_1' in json_result:
            df = pd.DataFrame(json_result['OutBlock_1'])
            print(f"✅ 방법 2 성공! {len(df)}개 종목 다운로드")
            
            # 컬럼명 변환
            column_map = {
                'ISU_SRT_CD': '단축코드',
                'ISU_ABBRV': '한글 종목약명',
                'MKT_NM': '시장구분',
                'SECT_TP_NM': '업종명'
            }
            df = df.rename(columns=column_map)
            return df
        else:
            raise Exception("JSON 응답에 데이터 없음")
            
    except Exception as e:
        print(f"❌ 방법 2 실패: {e}")
        return None


def method3_pykrx():
    """방법 3: pykrx 라이브러리 사용"""
    print("\n[방법 3] pykrx 라이브러리 방식 시도 중...")
    
    try:
        # pykrx 설치 시도
        try:
            from pykrx import stock
        except ImportError:
            print("📦 pykrx 설치 중...")
            import subprocess
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'pykrx', '--quiet'])
            from pykrx import stock
        
        from datetime import datetime
        today = datetime.today().strftime('%Y%m%d')
        
        # 코스피 + 코스닥 티커 가져오기
        kospi_tickers = stock.get_market_ticker_list(today, market="KOSPI")
        kosdaq_tickers = stock.get_market_ticker_list(today, market="KOSDAQ")
        all_tickers = kospi_tickers + kosdaq_tickers
        
        print(f"📊 총 {len(all_tickers)}개 종목 발견")
        
        # 종목명 가져오기
        stock_list = []
        for ticker in all_tickers:
            try:
                name = stock.get_market_ticker_name(ticker)
                market = "코스피" if ticker in kospi_tickers else "코스닥"
                stock_list.append({
                    '단축코드': ticker,
                    '한글 종목약명': name,
                    '시장구분': market,
                    '업종명': ''
                })
            except:
                pass
        
        df = pd.DataFrame(stock_list)
        print(f"✅ 방법 3 성공! {len(df)}개 종목 다운로드")
        return df
        
    except Exception as e:
        print(f"❌ 방법 3 실패: {e}")
        return None


def method4_investing():
    """방법 4: Investing.com 크롤링"""
    print("\n[방법 4] Investing.com 방식 시도 중...")
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        # Investing.com 한국 주식 리스트
        url = 'https://www.investing.com/stock-screener/?sp=country::37|sector::a|industry::a|equityType::a|exchange::a%3Ceq_market_cap;1'
        
        response = requests.get(url, headers=headers, timeout=30)
        
        # 간단한 HTML 파싱
        import re
        
        # 종목 코드 패턴 찾기
        codes = re.findall(r'data-symbol="([0-9]{6})"', response.text)
        names = re.findall(r'title="([^"]+)"', response.text)
        
        if codes and names:
            stock_list = []
            for i, code in enumerate(codes):
                if i < len(names):
                    stock_list.append({
                        '단축코드': code,
                        '한글 종목약명': names[i],
                        '시장구분': 'KRX',
                        '업종명': ''
                    })
            
            df = pd.DataFrame(stock_list)
            print(f"✅ 방법 4 성공! {len(df)}개 종목 다운로드")
            return df
        else:
            raise Exception("데이터 파싱 실패")
            
    except Exception as e:
        print(f"❌ 방법 4 실패: {e}")
        return None


def method5_naver_finance():
    """방법 5: 네이버 금융 크롤링"""
    print("\n[방법 5] 네이버 금융 방식 시도 중...")
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://finance.naver.com/'
        }
        
        all_stocks = []
        
        # 코스피 (1~40페이지 정도)
        print("📊 코스피 종목 수집 중...")
        for page in range(1, 41):
            try:
                url = f'https://finance.naver.com/sise/sise_market_sum.naver?sosok=0&page={page}'
                response = requests.get(url, headers=headers, timeout=10)
                
                df_list = pd.read_html(response.text)
                if df_list:
                    df = df_list[1]
                    df = df.dropna(subset=['종목명'])
                    
                    for _, row in df.iterrows():
                        all_stocks.append({
                            '단축코드': str(row['종목코드']).zfill(6) if '종목코드' in df.columns else '',
                            '한글 종목약명': row['종목명'],
                            '시장구분': '코스피',
                            '업종명': ''
                        })
                
                if page % 10 == 0:
                    print(f"  - {page}페이지 완료 ({len(all_stocks)}개 종목)")
                
                time.sleep(0.1)
            except:
                break
        
        # 코스닥 (1~40페이지 정도)
        print("📊 코스닥 종목 수집 중...")
        for page in range(1, 41):
            try:
                url = f'https://finance.naver.com/sise/sise_market_sum.naver?sosok=1&page={page}'
                response = requests.get(url, headers=headers, timeout=10)
                
                df_list = pd.read_html(response.text)
                if df_list:
                    df = df_list[1]
                    df = df.dropna(subset=['종목명'])
                    
                    for _, row in df.iterrows():
                        all_stocks.append({
                            '단축코드': str(row['종목코드']).zfill(6) if '종목코드' in df.columns else '',
                            '한글 종목약명': row['종목명'],
                            '시장구분': '코스닥',
                            '업종명': ''
                        })
                
                if page % 10 == 0:
                    print(f"  - {page}페이지 완료 ({len(all_stocks)}개 종목)")
                
                time.sleep(0.1)
            except:
                break
        
        if all_stocks:
            df = pd.DataFrame(all_stocks)
            print(f"✅ 방법 5 성공! {len(df)}개 종목 다운로드")
            return df
        else:
            raise Exception("종목 데이터 없음")
            
    except Exception as e:
        print(f"❌ 방법 5 실패: {e}")
        return None


def process_and_save(df_raw):
    """다운로드한 데이터를 가공하고 저장"""
    print("\n" + "="*60)
    print("🔄 데이터 가공 중...")
    print("="*60)
    
    # 필요한 컬럼 추출
    df = pd.DataFrame({
        '회사명': df_raw['한글 종목약명'].astype(str).str.strip(),
        '종목코드': df_raw['단축코드'].astype(str).str.strip().str.zfill(6),
        '시장구분': df_raw['시장구분'].astype(str) if '시장구분' in df_raw.columns else '기타',
        '업종명': df_raw['업종명'].astype(str) if '업종명' in df_raw.columns else ''
    })
    
    # 섹터 분류
    def classify_sector(row):
        name = row['회사명'].upper()
        industry = row['업종명']
        
        # AI/IT
        if any(k in name for k in ['NAVER', '네이버', '카카오', 'NC', '엔씨', '넥슨', '크래프톤', '펄어비스', '위메이드', '넷마블', 'SDS']):
            return 'AI'
        
        # 바이오/제약
        if any(k in name or k in industry for k in ['바이오', '제약', '셀트리온', '팜', '메디', '의약', '알테오젠', '휴젤', '유한', '한미약품', '종근당']):
            return '의약품'
        
        # 반도체
        if any(k in name or k in industry for k in ['삼성전자', 'SK하이닉스', '하이닉스', '반도체', 'DB하이텍', '한미반도체', 'ISC', '주성엔지니어링']):
            return '양자컴퓨터'
        
        # 2차전지
        if any(k in name or k in industry for k in ['LG에너지', '삼성SDI', 'SDI', '에코프로', '포스코퓨처', '2차전지', '배터리', '양극재']):
            return '2차전지'
        
        # 로봇
        if '로봇' in name:
            return '로봇'
        
        # 우주항공
        if any(k in name for k in ['에어로스페이스', '인텔리안', '넥스원', '항공', '우주']):
            return '우주항공'
        
        # 전기차
        if any(k in name for k in ['현대차', '기아', '전기차', 'EV']):
            return '전기차'
        
        return industry if industry and industry != 'nan' else '기타'
    
    df['섹터'] = df.apply(classify_sector, axis=1)
    
    # 최종 정리
    df_final = df[['회사명', '종목코드', '섹터']].copy()
    df_final = df_final.drop_duplicates(subset=['종목코드'])
    df_final = df_final[df_final['종목코드'].str.len() == 6]  # 6자리 코드만
    df_final = df_final.sort_values('종목코드').reset_index(drop=True)
    
    # 저장
    output_file = 'krx_stock_list.csv'
    df_final.to_csv(output_file, index=False, encoding='utf-8-sig')
    
    # 결과 출력
    print("\n" + "="*60)
    print("✅ 저장 완료!")
    print("="*60)
    print(f"📁 파일: {output_file}")
    print(f"📊 총 종목: {len(df_final):,}개")
    print("\n📌 섹터별 통계:")
    print("-"*60)
    
    sector_counts = df_final['섹터'].value_counts()
    for sector, count in sector_counts.head(15).items():
        print(f"   {sector:20s}: {count:>5,}개")
    
    print("="*60)
    return True


def main():
    """메인 함수: 여러 방법을 순차적으로 시도"""
    print("\n" + "="*60)
    print("🚀 KRX 전체 종목 다운로더 v3.0")
    print("="*60)
    print("📥 5가지 방법으로 다운로드 시도합니다...\n")
    
    methods = [
        ("KRX OTP 방식", method1_krx_otp),
        ("KRX JSON API", method2_krx_json),
        ("pykrx 라이브러리", method3_pykrx),
        ("Investing.com", method4_investing),
        ("네이버 금융", method5_naver_finance),
    ]
    
    for i, (name, method_func) in enumerate(methods, 1):
        print(f"\n{'='*60}")
        print(f"🔄 [{i}/5] {name} 시도 중...")
        print(f"{'='*60}")
        
        try:
            df = method_func()
            
            if df is not None and len(df) > 100:  # 최소 100개 이상이어야 성공
                print(f"\n✅ 성공! {name}으로 {len(df):,}개 종목 다운로드 완료")
                return process_and_save(df)
            else:
                print(f"⚠️  데이터 부족 ({len(df) if df is not None else 0}개)")
                
        except Exception as e:
            print(f"❌ 오류: {e}")
        
        if i < len(methods):
            print(f"\n⏳ 다음 방법 시도까지 3초 대기...")
            time.sleep(3)
    
    # 모든 방법 실패
    print("\n" + "="*60)
    print("❌ 모든 다운로드 방법 실패")
    print("="*60)
    print("\n💡 해결 방법:")
    print("1. 인터넷 연결 확인")
    print("2. 방화벽/보안 프로그램 확인")
    print("3. VPN 사용 시도")
    print("4. 다른 네트워크에서 시도 (모바일 핫스팟 등)")
    print("5. GitHub Actions에서 실행 (다른 서버에서 시도)")
    print("\n📌 GitHub Actions 실행 방법:")
    print("   1. 이 파일을 GitHub에 푸시")
    print("   2. GitHub Actions 탭에서 'Run workflow' 클릭")
    print("="*60)
    
    return False


if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)