# 그루북 업무 자동화 웹앱

그루북 포장전표 작업을 자동화하는 웹 애플리케이션입니다.
Excel 파일을 업로드하면 A4 PDF 포장전표를 자동으로 생성합니다.

## 지원 작업

- **내신노트** — 비법전수 내신노트 포장전표 (밴딩 30 고정)
- **분기별교재** — 분기별 교재 포장전표 (밴딩 파일에서 자동 읽기)
- **중간기말교재** — 중간/기말고사 교재 포장전표 (본책 · 미니북 · 교사용)

---

## 설치 및 실행

### 공통 사전 준비

**Python 3.10 이상** 이 필요합니다.

```bash
# 저장소 클론
git clone https://github.com/juhhoho/groobook-web.git
cd groobook-web
```

---

### Windows

**1. WeasyPrint 의존 라이브러리 설치**

GTK 런타임이 필요합니다.
아래 링크에서 GTK3 런타임 인스톨러를 받아 설치하세요.
https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases
(최신 `gtk3-runtime-*-x64.exe` 다운로드 후 실행)

설치 후 **PC 재시작**을 권장합니다.

**2. Python 패키지 설치 및 실행**

```bat
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

브라우저에서 http://127.0.0.1:8000 접속

---

### macOS

**1. WeasyPrint 의존 라이브러리 설치** (Homebrew 필요)

```bash
brew install pango glib
```

**2. 라이브러리 경로 설정** (최초 1회)

```bash
echo 'export DYLD_LIBRARY_PATH=/opt/homebrew/lib' >> ~/.zshrc
source ~/.zshrc
```

> Intel Mac의 경우 `/opt/homebrew` 대신 `/usr/local` 을 사용하세요.

**3. Python 패키지 설치 및 실행**

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

브라우저에서 http://127.0.0.1:8000 접속

---

### Linux (Ubuntu / Debian)

**1. WeasyPrint 의존 라이브러리 설치**

```bash
sudo apt update
sudo apt install -y libpango-1.0-0 libpangoft2-1.0-0 libgdk-pixbuf2.0-0
```

**2. Python 패키지 설치 및 실행**

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

브라우저에서 http://127.0.0.1:8000 접속

---

## AWS EC2 배포 (Ubuntu)

```bash
# 의존 라이브러리
sudo apt update
sudo apt install -y libpango-1.0-0 libpangoft2-1.0-0 libgdk-pixbuf2.0-0 nginx

# 앱 실행 (백그라운드)
pip install -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 8000 &

# Nginx 리버스 프록시 설정
sudo nano /etc/nginx/sites-available/groobook
```

Nginx 설정 내용:

```nginx
server {
    listen 80;
    server_name your-domain.duckdns.org;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/groobook /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

---

## 기술 스택

| 구분 | 기술 |
|------|------|
| 백엔드 | FastAPI, Python 3.10+ |
| PDF 생성 | WeasyPrint (HTML → PDF) |
| Excel 파싱 | openpyxl |
| 프론트엔드 | HTML / CSS / Vanilla JS |
