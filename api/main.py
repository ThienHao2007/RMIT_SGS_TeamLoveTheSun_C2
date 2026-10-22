from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .guard import admin_middleware
from .quorum import router as quorum_router

app = FastAPI(title="Quorum-Governed API Guard")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)
app.middleware("http")(admin_middleware)


@app.get("/data")
async def get_data():
    return {"data": "public"}


app.include_router(quorum_router)

# Serve Production UI
UI_DIST = Path(__file__).resolve().parent.parent / "ui" / "dist"
if UI_DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(UI_DIST / "assets")), name="assets")

    @app.api_route("/", methods=["GET", "HEAD"])
    async def serve_root():
        return FileResponse(UI_DIST / "index.html")

    @app.api_route("/{full_path:path}", methods=["GET", "HEAD"])
    async def serve_ui(full_path: str):
        # Do not intercept API paths
        api_roots = {"data", "policy", "policies", "limits", "quorum", "overview", "audit", "administrators"}
        if full_path.split("/", 1)[0] in api_roots:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Not Found")
        file_path = (UI_DIST / full_path).resolve()
        if not file_path.is_relative_to(UI_DIST.resolve()):
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Not Found")
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(UI_DIST / "index.html")
