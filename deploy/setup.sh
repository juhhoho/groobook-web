#!/bin/bash

# groobook-web 서버 초기 설정 스크립트 (Amazon Linux 2023)
# EC2에서 실행: bash deploy/setup.sh <DUCKDNS_TOKEN> <DUCKDNS_DOMAIN>

set -e

DUCKDNS_TOKEN=$1
DUCKDNS_DOMAIN=$2
APP_DIR=/home/ec2-user/groobook-web

if [ -z "$DUCKDNS_TOKEN" ] || [ -z "$DUCKDNS_DOMAIN" ]; then
    echo "사용법: bash deploy/setup.sh <DUCKDNS_TOKEN> <DUCKDNS_DOMAIN>"
    echo "예: bash deploy/setup.sh abc123token groobook"
    exit 1
fi

echo "=========================================="
echo "groobook-web AWS 배포 스크립트 시작"
echo "=========================================="

# 1. 시스템 업데이트
echo "[1/7] 시스템 업데이트 중..."
sudo dnf update -y

# 2. Python 및 필수 라이브러리 설치
echo "[2/7] Python 및 WeasyPrint 의존성 설치 중..."
sudo dnf install -y python3-pip python3 python3-devel
sudo dnf install -y pango gdk-pixbuf2 libffi-devel cairo

# 3. Nginx 설치
echo "[3/7] Nginx 설치 중..."
sudo dnf install -y nginx cronie

# 4. 프로젝트 환경 설정
echo "[4/7] Python 가상환경 및 패키지 설치 중..."
cd $APP_DIR
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

# 5. systemd 서비스 등록
echo "[5/7] systemd 서비스 등록 중..."
sudo cp deploy/groobook.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable groobook
sudo systemctl start groobook

# 6. Nginx 설정
# Amazon Linux 2023은 sites-available/sites-enabled 구조 없이 /etc/nginx/conf.d/ 사용
echo "[6/7] Nginx 리버스 프록시 설정 중..."
sudo cp deploy/nginx.conf /etc/nginx/conf.d/groobook.conf
sudo sed -i "s/groobook.duckdns.org/${DUCKDNS_DOMAIN}.duckdns.org/g" /etc/nginx/conf.d/groobook.conf
sudo sed -i "s|/home/ubuntu/|/home/ec2-user/|g" /etc/nginx/conf.d/groobook.conf
# 기본 nginx.conf의 server 블록 비활성화
sudo sed -i 's/^\s*server {/# server {/' /etc/nginx/nginx.conf || true
sudo nginx -t
sudo systemctl enable nginx
sudo systemctl start nginx

# 7. DuckDNS 자동 업데이트 설정
echo "[7/7] DuckDNS 자동 업데이트 설정 중..."
# crond 서비스 시작 (Amazon Linux 2023에서 필수)
sudo systemctl enable crond
sudo systemctl start crond

mkdir -p ~/duckdns
cat > ~/duckdns/duck.sh << EOF
#!/bin/bash
echo url="https://www.duckdns.org/update?domains=${DUCKDNS_DOMAIN}&token=${DUCKDNS_TOKEN}&ip=" | curl -k -o ~/duckdns/duck.log -K -
EOF
chmod +x ~/duckdns/duck.sh

# crontab 추가 (중복 방지)
(crontab -l 2>/dev/null | grep -v "duck.sh" || true; echo "*/5 * * * * ~/duckdns/duck.sh >/dev/null 2>&1") | crontab -

echo ""
echo "=========================================="
echo "✓ 초기 설정 완료!"
echo "=========================================="
echo ""
echo "다음 단계:"
echo "1. .env 파일 생성 (nano ${APP_DIR}/.env)"
echo "   - AUTH_CODE=<인증코드>"
echo "   - GMAIL_ADDRESS=<이메일>"
echo "   - GMAIL_APP_PASSWORD=<앱비밀번호>"
echo ""
echo "2. campus_emails.json 업로드"
echo ""
echo "3. .env 생성 후 서비스 재시작:"
echo "   sudo systemctl restart groobook"
echo ""
echo "4. systemd 서비스 상태 확인:"
echo "   sudo systemctl status groobook"
echo ""
echo "5. 도메인 접속: http://${DUCKDNS_DOMAIN}.duckdns.org"
echo ""
