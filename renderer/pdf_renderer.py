import os
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML as WeasyprintHTML

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")
_jinja_env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))


def render_pdf(slip_list: list, progress_cb=None, proc_type: str = "default") -> bytes:
    """
    slip_list → HTML → WeasyPrint PDF bytes
    proc_type: "midterm" → A4 가로 1장/페이지 6섹션 레이아웃
               기타     → A4 세로 5장/행 레이아웃
    """
    def cb(pct, msg):
        if progress_cb:
            progress_cb(pct, msg)

    cb(75, "HTML 렌더링 중...")

    if proc_type == "naeshin":
        template = _jinja_env.get_template("slip_naeshin.html")
        html_str = template.render(slips=slip_list)
    elif proc_type in ("midterm", "quarterly"):
        template = _jinja_env.get_template("slip_midterm.html")
        html_str = template.render(slips=slip_list, proc_type=proc_type)
    else:
        # 5장씩 행으로 묶기
        rows = [slip_list[i:i + 5] for i in range(0, len(slip_list), 5)]
        template = _jinja_env.get_template("slip.html")
        html_str = template.render(rows=rows)

    cb(90, "PDF 변환 중...")
    pdf_bytes = WeasyprintHTML(string=html_str).write_pdf()

    cb(100, "완료!")
    return pdf_bytes
