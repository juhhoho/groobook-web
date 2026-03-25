from io import BytesIO
import openpyxl


def process_naeshin(file_bytes: bytes, progress_cb=None) -> list:
    """
    비법전수내신노트 Excel 분석 → slip list 반환

    slip 구조 (8요소):
    [캠퍼스, "비법전수 내신노트", ' ', ' ', 수량, 총덩이수, '-', 현재번호]
    정렬: 캠퍼스 열 인덱스 오름차순 (Excel 원본 순서 유지)
    """
    def cb(pct, msg):
        if progress_cb:
            progress_cb(pct, msg)

    cb(10, "파일 읽는 중...")
    workbook = openpyxl.load_workbook(BytesIO(file_bytes))
    sheet1 = workbook.worksheets[0]

    cb(30, "데이터 추출 중...")
    banding = 30

    # Row 3: 캠퍼스명 ("계" 전까지, None 건너뜀)
    campus_info = []
    for cell in sheet1[3]:
        if cell.value is None:
            continue
        elif cell.value == "계":
            break
        else:
            campus_info.append(cell.value)

    # Row 4: 수량 (첫 셀 건너뛰고, 캠퍼스 수만큼)
    total_info = []
    n = 0
    length = len(campus_info)
    for cell in sheet1[4]:
        if n == 0:
            n += 1
            continue
        elif n == length + 1:
            break
        else:
            total_info.append(cell.value)
            n += 1

    cb(55, "포장 계산 중...")

    # 밴딩 분할
    banding_info = []
    for qty in total_info:
        tmp = []
        num_a = qty // banding
        num_b = qty % banding
        for _ in range(num_a):
            tmp.append(banding)
        if num_b != 0:
            tmp.append(num_b)
        banding_info.append(tmp)

    # slip list 생성 (캠퍼스 열 순서 유지)
    slip_list = []
    for i in range(len(banding_info)):
        total_packing = len(banding_info[i])
        for j, qty in enumerate(banding_info[i]):
            slip_list.append([
                campus_info[i],
                "비법전수 내신노트",
                ' ',
                ' ',
                qty,
                total_packing,
                '-',
                j + 1,
            ])

    cb(75, "완료 준비 중...")
    workbook.close()
    return slip_list
