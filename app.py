import os
import sys
import asyncio
import logging

# Fix for Playwright subprocesses on Windows with Uvicorn/asyncio
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, Response
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field
from scraper import get_attendance
from report_generator import generate_pdf_report, generate_txt_report

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("mits_ims_web")


app = FastAPI(
    title="MITS IMS Attendance Web API",
    description="Web service to scrape and view MITS IMS student attendance",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["Content-Type", "Authorization", "Accept", "Origin", "X-Requested-With"],
)

@app.on_event("startup")
async def startup_event():
    try:
        logger.info("Auto-verifying Playwright Chromium browser installation on startup...")
        import subprocess
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=False)
        logger.info("Playwright Chromium browser verification finished.")
    except Exception as e:
        logger.warning(f"Playwright auto-install check notice: {e}")


# Mount static files directory
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir, exist_ok=True)

app.mount("/static", StaticFiles(directory=static_dir), name="static")



class AttendanceRequest(BaseModel):
    username: str = Field(..., description="MITS IMS Student ID / Register Number")
    password: str = Field(..., description="MITS IMS Password")


class ExportReportRequest(BaseModel):
    student_name: Optional[str] = "Student"
    register_number: Optional[str] = "N/A"
    data: List[dict] = []
    timestamp: Optional[str] = None





@app.middleware("http")
async def add_security_and_seo_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response


@app.get("/robots.txt", response_class=FileResponse)
async def serve_robots():
    robots_path = os.path.join(static_dir, "robots.txt")
    if os.path.exists(robots_path):
        return FileResponse(robots_path, media_type="text/plain")
    return Response("User-agent: *\nAllow: /\n", media_type="text/plain")


@app.get("/sitemap.xml", response_class=FileResponse)
async def serve_sitemap():
    sitemap_path = os.path.join(static_dir, "sitemap.xml")
    if os.path.exists(sitemap_path):
        return FileResponse(sitemap_path, media_type="application/xml")
    return Response("<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'></urlset>", media_type="application/xml")


@app.get("/", response_class=FileResponse)
async def serve_index():
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return JSONResponse({"message": "MITS IMS Attendance Web API is running!"})


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    fav_path = os.path.join(static_dir, "favicon.ico")
    if os.path.exists(fav_path):
        return FileResponse(fav_path)
    return FileResponse(os.path.join(static_dir, "logo.png"))




@app.get("/manifest.json", response_class=FileResponse)
async def serve_manifest():
    manifest_path = os.path.join(static_dir, "manifest.json")
    return FileResponse(manifest_path, media_type="application/manifest+json")


@app.get("/service-worker.js", response_class=FileResponse)
async def serve_service_worker():
    sw_path = os.path.join(static_dir, "service-worker.js")
    return FileResponse(
        sw_path,
        media_type="application/javascript",
        headers={"Service-Worker-Allowed": "/", "Cache-Control": "no-cache"}
    )


@app.get("/offline.html", response_class=FileResponse)
async def serve_offline():
    offline_path = os.path.join(static_dir, "offline.html")
    return FileResponse(offline_path)


@app.get("/install", response_class=FileResponse)
@app.get("/install.html", response_class=FileResponse)
async def serve_install_page():
    install_path = os.path.join(static_dir, "install.html")
    if os.path.exists(install_path):
        return FileResponse(install_path)
    return FileResponse(os.path.join(static_dir, "index.html"))


@app.get("/404", response_class=FileResponse)
@app.get("/404.html", response_class=FileResponse)
async def serve_404_page():
    notfound_path = os.path.join(static_dir, "404.html")
    if os.path.exists(notfound_path):
        return FileResponse(notfound_path, status_code=404)
    return JSONResponse({"error": "Page not found"}, status_code=404)


@app.exception_handler(404)
async def custom_404_handler(request, exc):
    notfound_path = os.path.join(static_dir, "404.html")
    if os.path.exists(notfound_path):
        return FileResponse(notfound_path, status_code=404)
    return JSONResponse({"error": "Page not found"}, status_code=404)


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "MITS IMS Attendance Web"}


@app.post("/api/attendance")
async def fetch_attendance(req: AttendanceRequest):
    username = req.username.strip()
    password = req.password.strip()

    if not username or not password:
        return JSONResponse(status_code=400, content={"success": False, "error": "Student ID and Password are required."})

    logger.info(f"Received attendance request for user: {username}")
    
    try:
        result = await get_attendance(username, password)
        
        if isinstance(result, dict) and "error" in result:
            err_msg = str(result["error"]).strip()
            logger.warning(f"Scraping error for {username}: {err_msg}")
            return JSONResponse(status_code=400, content={"success": False, "error": err_msg})

        if isinstance(result, dict) and "records" in result:
            data = result["records"]
            student_name = result.get("student_name")
        else:
            data = result
            student_name = None

        logger.info(f"Successfully fetched attendance for {username} with {len(data)} subjects (Student Name: {student_name}).")
        return {"success": True, "student_name": student_name, "data": data}
        
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        logger.error(f"Unexpected server error for {username}:\n{tb}")
        err_detail = str(e).replace('\\', ' ').strip()
        if not err_detail:
            err_detail = f"{type(e).__name__} occurred"
        return JSONResponse(status_code=500, content={"success": False, "error": f"Server error: {err_detail}"})


@app.post("/api/export/pdf")
async def export_pdf(req: ExportReportRequest):
    try:
        pdf_bytes = generate_pdf_report(req.student_name, req.register_number, req.data, req.timestamp)
        filename = f"Attendance_Report_{req.register_number or 'Student'}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        logger.error(f"PDF export error: {e}")
        return JSONResponse(status_code=500, content={"success": False, "error": f"Failed to generate PDF report: {str(e)}"})


@app.post("/api/export/txt")
async def export_txt(req: ExportReportRequest):
    try:
        txt_bytes = generate_txt_report(req.student_name, req.register_number, req.data, req.timestamp)
        filename = f"Attendance_Report_{req.register_number or 'Student'}.txt"
        return Response(
            content=txt_bytes,
            media_type="text/plain",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        logger.error(f"TXT export error: {e}")
        return JSONResponse(status_code=500, content={"success": False, "error": f"Failed to generate TXT report: {str(e)}"})


# Mount static directory at root / for direct asset access
app.mount("/", StaticFiles(directory=static_dir, html=True), name="root_static")


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"Starting server on port {port}...")
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=True)
