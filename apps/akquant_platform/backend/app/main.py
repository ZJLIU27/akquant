"""AKQuant Platform FastAPI application."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .positions.routes import router as positions_router
from .intraday.routes import router as data_router
from .jobs.routes import router as jobs_router

app = FastAPI(title="AKQuant Platform", version="0.1.0")

# API routes
app.include_router(positions_router)
app.include_router(data_router)
app.include_router(jobs_router)

# Serve frontend static files in production
_frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _frontend_dist.exists():
    from fastapi.responses import FileResponse

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve the SPA frontend — fallback to index.html for client-side routing."""
        file = _frontend_dist / full_path
        if file.exists() and file.is_file():
            return FileResponse(file)
        return FileResponse(_frontend_dist / "index.html")

    # Mount assets
    app.mount("/assets", StaticFiles(directory=_frontend_dist / "assets"), name="assets")
