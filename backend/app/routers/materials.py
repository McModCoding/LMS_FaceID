from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.material import MaterialList, MaterialOut, MaterialUpdate
from app.services import material_service as service

router = APIRouter(tags=["Materials"])


@router.get("/classes/{class_id}/materials", response_model=MaterialList)
def list_materials(class_id: int, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                   db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.list_materials(db, user, class_id, page, page_size)


@router.post("/classes/{class_id}/materials", response_model=MaterialOut, status_code=201)
async def create_material(class_id: int, title: str = Form(...), description: str | None = Form(None),
                          url: str | None = Form(None), file: UploadFile | None = File(None),
                          db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    content = await file.read(settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024 + 1) if file else None
    return service.material_out(service.create_material(
        db, user, class_id, title, description, url,
        file.filename if file else None, file.content_type if file else None, content))


@router.patch("/materials/{material_id}", response_model=MaterialOut)
def update_material(material_id: int, data: MaterialUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.material_out(service.update_material(db, user, material_id, data))


@router.delete("/materials/{material_id}", status_code=204)
def delete_material(material_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    service.delete_material(db, user, material_id)
    return Response(status_code=204)


@router.get("/materials/{material_id}/file")
def download_material(material_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    path, filename = service.download_material(db, user, material_id)
    return FileResponse(path, filename=filename, media_type="application/octet-stream", headers={"X-Content-Type-Options": "nosniff"})
