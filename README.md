# UsedMarket

## 필수 패키지 설치

프로젝트 루트 디렉토리에서 아래 명령어로 필요한 패키지를 설치합니다.
pip install -r requirements.txt

## 환경 변수 설정
프로젝트 루트 디렉토리에 .env 파일을 생성하고, 아래와 같은 환경 변수를 설정한다.
SECRET_KEY=your_secret_key
DATABASE=market.db
DEFAULT_ADMIN_USERNAME=superadmin
DEFAULT_ADMIN_PASSWORD=S3cur3Pass!2025

## 데이터베이스 초기화
프로젝트를 처음 실행하는 경우, init_db() 함수가 데이터 베이스 구조를 설정한다.
python run.py

## 애플리케이션 실행
서버를 실행해 웹 애플리케이션을 시작한다.
python run.py

## 웹 브라우저에서 확인
웹 브라우저에서 http://localhost:5000에 접속하여 애플리케이션을 사용한다.

