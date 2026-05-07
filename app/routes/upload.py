from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
import shutil
import os

router = APIRouter()
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {".txt", ".pdf", ".json", ".csv", ".md"}


@router.post("/", summary="Upload an MEP drawing or specification file")
async def upload_file(file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {sorted(ALLOWED_EXTENSIONS)}"
        )

    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return {
        "filename": file.filename,
        "size_bytes": os.path.getsize(file_path),
        "message": "File uploaded successfully. Call GET /compliance/report?filename=<name> to check compliance.",
        "next_step": f"/compliance/report?filename={file.filename}"
    }


@router.get("/list", summary="List all uploaded files")
def list_uploads():
    files = []
    for f in os.listdir(UPLOAD_DIR):
        path = os.path.join(UPLOAD_DIR, f)
        files.append({
            "filename": f,
            "size_bytes": os.path.getsize(path),
        })
    return {"uploaded_files": files, "count": len(files)}
