"""
考古文献解析 API — FastAPI backend
Parses Chinese archaeological reports into structured tomb data.
"""

import os
import tempfile
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from kaogu_parser import auto_parse

app = FastAPI(
    title="考古文献解析 API",
    description="Parse Chinese archaeological reports into structured tomb data",
    version="1.0.0",
)

# CORS — allow Netlify frontend and local dev
ALLOWED_ORIGINS = [
    "https://kaogu.app",
    "https://kaogu-parser.netlify.app",
    "https://*.netlify.app",
    "http://localhost:5173",
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "kaogu-parser"}


@app.post("/api/parse")
async def parse_report(
    file: UploadFile = File(...),
    report_name: str = Form(default=""),
):
    """Upload an archaeological report (.md or .txt) and get structured tomb data."""

    # Validate file type
    filename = file.filename or "unknown.txt"
    if not filename.lower().endswith(('.md', '.txt')):
        raise HTTPException(
            status_code=400,
            detail="仅支持 .md 或 .txt 格式文件。请先将PDF转换为markdown或txt格式。"
        )

    # Read content
    try:
        raw = await file.read()
    except Exception:
        raise HTTPException(status_code=400, detail="文件读取失败")

    if len(raw) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"文件过大。最大支持 {MAX_FILE_SIZE // (1024*1024)}MB。"
        )

    # Decode — try UTF-8 first, then GBK (common for Chinese docs)
    content = None
    for encoding in ['utf-8', 'gbk', 'gb2312', 'big5', 'latin-1']:
        try:
            content = raw.decode(encoding)
            break
        except (UnicodeDecodeError, LookupError):
            continue

    if content is None:
        raise HTTPException(status_code=400, detail="文件编码无法识别，请使用UTF-8编码。")

    if not content.strip():
        raise HTTPException(status_code=400, detail="文件内容为空。")

    # Use provided name or filename
    name = report_name.strip() or filename.rsplit('.', 1)[0]

    # Parse
    try:
        parser = auto_parse(name, content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"解析失败: {str(e)}")

    result = parser.to_json()
    result["报告名称"] = name
    result["文件名"] = filename
    result["墓葬总数"] = len(parser.tombs)
    result["器物总数"] = sum(len(t.get('随葬器物', [])) for t in parser.tombs)

    return JSONResponse(content=result)


@app.post("/api/export/csv")
async def export_csv(
    file: UploadFile = File(...),
    report_name: str = Form(default=""),
):
    """Upload a report and get CSV export."""
    filename = file.filename or "unknown.txt"
    if not filename.lower().endswith(('.md', '.txt')):
        raise HTTPException(status_code=400, detail="仅支持 .md 或 .txt 格式文件。")

    raw = await file.read()
    if len(raw) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="文件过大。")

    content = None
    for encoding in ['utf-8', 'gbk', 'gb2312', 'big5', 'latin-1']:
        try:
            content = raw.decode(encoding)
            break
        except (UnicodeDecodeError, LookupError):
            continue

    if content is None:
        raise HTTPException(status_code=400, detail="文件编码无法识别。")

    name = report_name.strip() or filename.rsplit('.', 1)[0]
    parser = auto_parse(name, content)
    csv_content = parser.to_csv_string()

    return Response(
        content=csv_content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{name}_tombs.csv"'}
    )


@app.post("/api/export/markdown")
async def export_markdown(
    file: UploadFile = File(...),
    report_name: str = Form(default=""),
):
    """Upload a report and get Markdown export."""
    filename = file.filename or "unknown.txt"
    if not filename.lower().endswith(('.md', '.txt')):
        raise HTTPException(status_code=400, detail="仅支持 .md 或 .txt 格式文件。")

    raw = await file.read()
    if len(raw) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="文件过大。")

    content = None
    for encoding in ['utf-8', 'gbk', 'gb2312', 'big5', 'latin-1']:
        try:
            content = raw.decode(encoding)
            break
        except (UnicodeDecodeError, LookupError):
            continue

    if content is None:
        raise HTTPException(status_code=400, detail="文件编码无法识别。")

    name = report_name.strip() or filename.rsplit('.', 1)[0]
    parser = auto_parse(name, content)
    md_content = parser.to_markdown_string()

    return Response(
        content=md_content.encode('utf-8'),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{name}_tombs.md"'}
    )
