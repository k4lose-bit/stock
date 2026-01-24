import requests
import pandas as pd
from io import BytesIO
import time

def download_krx_stock_list():
    """
    KRX 상장법인목록을 다운로드하여 CSV로 저장
    """
    print("📥 KRX 상장법인목록 다운로드 시작...")
    
    try:
        # KRX OpenAPI - 상장법인목록 다운로드
        gen_otp_url = 'http://data.krx.co.kr/comm/fileDn/GenerateOTP/generate.cmd'
        
        gen_otp_data = {
            'mktId': 'ALL',  # ALL: 전체, STK: 코스피, KSQ: 코스닥
            'share': '1',
            'csvxls_isNo': 'false',
            'name': 'fileDown',
            'url': 'dbms/MDC/STAT/standard/MDCSTAT01901'
        }
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'http://data.krx.co.kr/'
        }
        
        # OTP 생성
        print("🔑 OTP 생성 중...")
        otp_response = requests.post(gen_otp_url, data=gen_otp_data, headers=headers)
        otp = otp_response.text
        
        if not otp:
            raise Exception("OTP 생성 실패")
        
        print(f"✅ OTP 생성 완료: {otp[:20]}...")
        
        time.sleep(1)  # 서버 부하 방지
        
        # 실제 데이터 다운로드
        print("📊 데이터 다운로드 중...")
        down_url = 'http://data.krx.co.kr/comm/fileDn/download_csv/download.cmd'
        down_data = {'code': otp}
        
        response = requests.post(down_url, data=down_data, headers=headers)
        response.raise_for_status()
        
        # CSV 파싱 (KRX는 EUC-KR 인코딩 사용)
        print("🔄 데이터 파싱 중...")
        df = pd.read_csv(BytesIO(response.content), encoding='EUC-KR')
        
        print(f"📈 원본 데이터: {len(df)}개 종목")
        
        # 필요한 컬럼만 추출
        df_result = pd.DataFrame({
            '회사명': df['한글 종목약명'],
            '종목코드': df['단축코드'].astype(str).str.zfill(6),
            '시장구분': df['시장구분'],
            '업종명': df['업종명']
        })
        
        # 섹터 분류 함수
        def classify_sector(row):
            name = str(row['회사명']).upper()
            industry = str(row['업종명'])
            
            # AI 관련
            ai_keywords = [
                'NAVER', '네이버', '카카오', '엔씨소프트', 'NC', '넥슨', 
                '크래프톤', '펄어비스', '컴투스', '위메이드', '데브시스터즈',
                '솔루션', 'AI', '인공지능', '빅데이터', '클라우드'
            ]
            if any(k in name for k in ai_keywords):
                return 'AI'
            
            # 의약품/바이오
            bio_keywords = [
                '바이오', '제약', '셀트리온', '삼성바이오', '팜', 'PHARM',
                '메디', '의약', '헬스케어', '알테오젠', '휴젤', '유한양행',
                '한미약품', '종근당', '대웅', '녹십자', '파마'
            ]
            if any(k in name or k in industry for k in bio_keywords):
                return '의약품'
            
            # 반도체/양자컴퓨터
            semi_keywords = [
                '삼성전자', 'SK하이닉스', '하이닉스', 'DB하이텍', 
                '한미반도체', '반도체', '테스', 'ISC', '주성엔지니어링',
                '원익IPS', '유진테크', 'HPSP', '반도'
            ]
            if any(k in name or k in industry for k in semi_keywords):
                return '양자컴퓨터'
            
            # 2차전지/배터리
            battery_keywords = [
                'LG에너지솔루션', '삼성SDI', 'SK온', '포스코퓨처엠',
                '에코프로', '2차전지', '배터리', '양극재', '음극재'
            ]
            if any(k in name or k in industry for k in battery_keywords):
                return '2차전지'
            
            # 로봇
            robot_keywords = [
                '로봇', '휴림로봇', '레인보우로보틱스', '한화로봇', 
                '유진로봇', '로보티즈'
            ]
            if any(k in name for k in robot_keywords):
                return '로봇'
            
            # 우주항공
            space_keywords = [
                '한화에어로스페이스', '인텔리안테크', 'LIG넥스원',
                '쎄트렉아이', '케이에스피', '항공', '우주', '위성'
            ]
            if any(k in name or k in industry for k in space_keywords):
                return '우주항공'
            
            # 기본값: 업종명 사용
            return industry if industry and industry != 'nan' else '기타'
        
        df_result['섹터'] = df_result.apply(classify_sector, axis=1)
        
        # 최종 컬럼 선택
        df_final = df_result[['회사명', '종목코드', '섹터']].copy()
        
        # 중복 제거 및 정렬
        df_final = df_final.drop_duplicates(subset=['종목코드']).sort_values('종목코드').reset_index(drop=True)
        
        # CSV 저장
        output_file = 'krx_stock_list.csv'
        df_final.to_csv(output_file, index=False, encoding='utf-8-sig')
        
        print(f"\n✅ 성공!")
        print(f"📁 파일: {output_file}")
        print(f"📊 총 종목 수: {len(df_final):,}개")
        
        # 섹터별 통계
        print("\n📌 섹터별 통계:")
        sector_counts = df_final['섹터'].value_counts()
        for sector, count in sector_counts.head(10).items():
            print(f"   - {sector}: {count}개")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = download_krx_stock_list()
    exit(0 if success else 1)