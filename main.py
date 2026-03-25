import threading
import uuid
from io import BytesIO

from urllib.parse import quote
from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request

from processors.naeshin import process_naeshin
from processors.quarterly import process_quarterly
from processors.midterm import process_midterm
from renderer.pdf_renderer import render_pdf

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# 인메모리 작업 저장소
tasks: dict[str, dict] = {}


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


# ──────────────── API 라우트 ────────────────

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
    })


@app.get("/api/download/{task_id}")
async def download(task_id: str):
    task = tasks.get(task_id)
    if not task or task["status"] != "done":
        raise HTTPException(status_code=404, detail="완성된 파일이 없습니다.")
    pdf_bytes = task["result_bytes"]
    filename = task["filename"]
    # 다운로드 후 메모리에서 제거
    tasks.pop(task_id, None)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )
