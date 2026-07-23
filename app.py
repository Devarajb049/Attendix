import os
import sys
import asyncio
import logging

# Fix for Playwright subprocesses on Windows with Uvicorn/asyncio
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from scraper import get_attendance

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
static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir, exist_ok=True)

app.mount("/static", StaticFiles(directory=static_dir), name="static")


class AttendanceRequest(BaseModel):
    username: str = Field(..., description="MITS IMS Student ID / Register Number")
    password: str = Field(..., description="MITS IMS Password")


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


@app.get("/manifest.json", include_in_schema=False)
async def manifest():
    manifest_path = os.path.join(static_dir, "manifest.json")
    if os.path.exists(manifest_path):
        return FileResponse(manifest_path)
    return JSONResponse({"error": "manifest not found"}, status_code=404)



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
        
        logger.info(f"Successfully fetched attendance for {username} with {len(result)} subjects.")
        return {"success": True, "data": result}
        
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        logger.error(f"Unexpected server error for {username}:\n{tb}")
        err_detail = str(e).replace('\\', ' ').strip()
        if not err_detail:
            err_detail = f"{type(e).__name__} occurred"
        return JSONResponse(status_code=500, content={"success": False, "error": f"Server error: {err_detail}"})




if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"Starting server on port {port}...")
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=True)
