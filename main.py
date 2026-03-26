import threading
import uuid
from io import BytesIO
import os

from urllib.parse import quote
from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, Response, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from typing import List
from itsdangerous import URLSafeTimedSerializer, BadSignature
from dotenv import load_dotenv

from processors.naeshin import process_naeshin
from processors.quarterly import process_quarterly
from processors.midterm import process_midterm
from processors.email_sender import scan_files, send_billing_emails
from renderer.pdf_renderer import render_pdf

load_dotenv()

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# 인메모리 작업 저장소
tasks: dict[str, dict] = {}

# 이메일 스캔 임시 저장소
email_scans: dict[str, dict] = {}

# ──────────────── 세션 및 인증 설정 ────────────────

SESSION_SECRET = os.getenv("SESSION_SECRET", "dev-fallback-secret-key")
APP_PASSWORD = os.getenv("APP_PASSWORD", "")
serializer = URLSafeTimedSerializer(SESSION_SECRET)
SESSION_COOKIE = "groobook_session"
SESSION_MAX_AGE = 60 * 60 * 24 * 7  # 7일


def verify_session(token: str) -> bool:
    """세션 토큰 검증"""
    if not token:
        return False
    try:
        serializer.loads(token, max_age=SESSION_MAX_AGE)
        return True
    except BadSignature:
        return False


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """모든 요청에 대해 인증 여부 확인"""
    # 로그인 페이지와 정적 파일은 예외
    if request.url.path.startswith("/login") or request.url.path.startswith("/static"):
        return await call_next(request)

    token = request.cookies.get(SESSION_COOKIE)
    if not verify_session(token):
        # API 요청이면 JSON 401 반환, 페이지 요청이면 /login으로 리다이렉트
        if request.url.path.startswith("/api"):
            return JSONResponse({"detail": "로그인이 필요합니다."}, status_code=401)
        return RedirectResponse("/login", status_code=302)

    return await call_next(request)


# ──────────────── 로그인 라우트 ────────────────

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request=request, name="login.html")


@app.post("/login")
async def login(request: Request, password: str = Form(...)):
    """비밀번호 검증 후 세션 쿠키 발급"""
    if password != APP_PASSWORD:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"error": "비밀번호가 올바르지 않습니다."},
            status_code=400,
        )

    token = serializer.dumps("authenticated")
    response = RedirectResponse("/", status_code=302)
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="Lax",
    )
    return response


@app.post("/logout")
async def logout():
    """세션 쿠키 삭제 후 로그인 페이지로 리다이렉트"""
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie(SESSION_COOKIE)
    return response


# ──────────────── 페이지 라우트 ────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


@app.get("/packaging", response_class=HTMLResponse)
async def packaging(request: Request):
    return templates.TemplateResponse(request=request, name="packaging.html")


@app.get("/naeshin", response_class=HTMLResponse)
async def naeshin_page(request: Request):
    return templates.TemplateResponse(request=request, name="work.html", context={
        "title": "내신노트",
        "type": "naeshin",
        "show_banding": False,
    })


@app.get("/quarterly", response_class=HTMLResponse)
async def quarterly_page(request: Request):
    return templates.TemplateResponse(request=request, name="work.html", context={
        "title": "분기별교재",
        "type": "quarterly",
        "show_banding": False,
    })


@app.get("/midterm", response_class=HTMLResponse)
async def midterm_page(request: Request):
    return templates.TemplateResponse(request=request, name="work.html", context={
        "title": "중간기말교재",
        "type": "midterm",
        "show_banding": True,
    })


@app.get("/email", response_class=HTMLResponse)
async def email_page(request: Request):
    return templates.TemplateResponse(request=request, name="email.html")


# ──────────────── 포장전표 API ────────────────

@app.post("/api/process/{proc_type}")
async def process(
    proc_type: str,
    file: UploadFile = File(...),
    main_banding: int = Form(20),
    mini_banding: int = Form(70),
    teacher_banding: int = Form(15),
):
    if proc_type not in ("naeshin", "quarterly", "midterm"):
        raise HTTPException(status_code=400, detail="알 수 없는 작업 유형입니다.")

    file_bytes = await file.read()
    task_id = str(uuid.uuid4())
    original_name = file.filename.rsplit('.', 1)[0]
    tasks[task_id] = {
        "status": "processing",
        "progress": 0,
        "message": "준비 중...",
        "result_bytes": None,
        "filename": f"{original_name}_{task_id[:8]}.pdf",
        "error": None,
    }

    def run():
        def progress_cb(pct, msg):
            tasks[task_id]["progress"] = pct
            tasks[task_id]["message"] = msg

        try:
            if proc_type == "naeshin":
                slip_list = process_naeshin(file_bytes, progress_cb)
            elif proc_type == "quarterly":
                slip_list = process_quarterly(file_bytes, progress_cb)
            else:
                slip_list = process_midterm(
                    file_bytes, main_banding, mini_banding, teacher_banding, progress_cb
                )

            pdf_bytes = render_pdf(slip_list, progress_cb, proc_type=proc_type)
            tasks[task_id]["result_bytes"] = pdf_bytes
            tasks[task_id]["status"] = "done"
        except Exception as e:
            tasks[task_id]["status"] = "error"
            tasks[task_id]["error"] = str(e)

    threading.Thread(target=run, daemon=True).start()
    return JSONResponse({"task_id": task_id})


@app.get("/api/progress/{task_id}")
async def get_progress(task_id: str):
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다.")
    return JSONResponse({
        "status": task["status"],
        "progress": task["progress"],
        "message": task["message"],
        "error": task.get("error"),
        "email_result": task.get("email_result"),
    })


@app.get("/api/download/{task_id}")
async def download(task_id: str):
    task = tasks.get(task_id)
    if not task or task["status"] != "done":
        raise HTTPException(status_code=404, detail="완성된 파일이 없습니다.")
    pdf_bytes = task["result_bytes"]
    filename = task["filename"]
    tasks.pop(task_id, None)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


# ──────────────── 이메일 API ────────────────

@app.post("/api/email/scan")
async def email_scan(files: List[UploadFile] = File(...)):
    """파일 업로드 → 파일명 파싱 → 스캔 결과 반환"""
    file_list = []
    for f in files:
        content = await f.read()
        file_list.append({"filename": f.filename, "bytes": content})

    result = scan_files(file_list)

    if not result["groups"]:
        raise HTTPException(status_code=400, detail="패턴에 맞는 청구서 파일이 없습니다.\n파일명 형식: YYYY년 MM월 캠퍼스명 청구서_내신교재.xlsx")

    scan_id = str(uuid.uuid4())
    email_scans[scan_id] = result

    return JSONResponse({
        "scan_id": scan_id,
        "preview": result["preview"],
        "total_groups": len(result["groups"]),
    })


@app.post("/api/email/send")
async def email_send(
    scan_id: str = Form(...),
    additional_msg: str = Form(""),
):
    """스캔된 파일 그룹으로 이메일 발송 시작"""
    scan = email_scans.get(scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="스캔 결과를 찾을 수 없습니다. 다시 스캔해주세요.")

    task_id = str(uuid.uuid4())
    tasks[task_id] = {
        "status": "processing",
        "progress": 0,
        "message": "준비 중...",
        "result_bytes": None,
        "filename": "",
        "error": None,
        "email_result": None,
    }

    groups = scan["groups"]

    def run():
        def progress_cb(pct, msg):
            tasks[task_id]["progress"] = pct
            tasks[task_id]["message"] = msg

        try:
            result = send_billing_emails(groups, additional_msg, progress_cb)
            tasks[task_id]["status"] = "done"
            tasks[task_id]["email_result"] = result
            email_scans.pop(scan_id, None)
        except Exception as e:
            tasks[task_id]["status"] = "error"
            tasks[task_id]["error"] = str(e)

    threading.Thread(target=run, daemon=True).start()
    return JSONResponse({"task_id": task_id})
