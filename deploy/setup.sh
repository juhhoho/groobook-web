#!/bin/bash

# groobook-web 서버 초기 설정 스크립트
# EC2에서 실행: bash deploy/setup.sh <DUCKDNS_TOKEN> <DUCKDNS_DOMAIN>

set -e

DUCKDNS_TOKEN=$1
DUCKDNS_DOMAIN=$2

if [ -z "$DUCKDNS_TOKEN" ] || [ -z "$DUCKDNS_DOMAIN" ]; then
    echo "사용법: bash deploy/setup.sh <DUCKDNS_TOKEN> <DUCKDNS_DOMAIN>"
    echo "예: bash deploy/setup.sh abc123token groobook"
    exit 1
fi

echo "=========================================="
echo "groobook-web AWS 배포 스크립트 시작"
echo "=========================================="

# 1. 시스템 업데이트
echo "[1/6] 시스템 업데이트 중..."
sudo apt update
sudo apt upgrade -y

# 2. Python 및 필수 라이브러리 설치
echo "[2/6] Python 및 WeasyPrint 의존성 설치 중..."
sudo apt install -y python3-pip python3-venv
sudo apt install -y libpango-1.0-0 libpangoft2-1.0-0 libgdk-pixbuf2.0-0

# 3. Nginx 설치
echo "[3/6] Nginx 설치 중..."
sudo apt install -y nginx

# 4. 프로젝트 환경 설정
echo "[4/6] Python 가상환경 및 패키지 설치 중..."
cd /home/ubuntu/groobook-web
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

# 5. systemd 서비스 등록
echo "[5/6] systemd 서비스 등록 중..."
sudo cp deploy/groobook.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable groobook
sudo systemctl start groobook

# 6. Nginx 설정
echo "[6/6] Nginx 리버스 프록시 설정 중..."
sudo cp deploy/nginx.conf /etc/nginx/sites-available/groobook
sudo sed -i "s/groobook.duckdns.org/${DUCKDNS_DOMAIN}.duckdns.org/g" /etc/nginx/sites-available/groobook
sudo rm -f /etc/nginx/sites-enabled/default
sudo ln -sf /etc/nginx/sites-available/groobook /etc/nginx/sites-enabled/groobook
sudo nginx -t
sudo systemctl reload nginx

# 7. DuckDNS 자동 업데이트 설정
echo "[7/7] DuckDNS 자동 업데이트 설정 중..."
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
echo "1. .env 파일 생성 (nano .env)"
echo "   - AUTH_CODE=<인증코드>"
echo "   - GMAIL_ADDRESS=<이메일>"
echo "   - GMAIL_APP_PASSWORD=<앱비밀번호>"
echo ""
echo "2. campus_emails.json 업로드"
echo ""
echo "3. systemd 서비스 상태 확인:"
echo "   sudo systemctl status groobook"
echo ""
echo "4. 도메인 접속: http://${DUCKDNS_DOMAIN}.duckdns.org"
echo ""
