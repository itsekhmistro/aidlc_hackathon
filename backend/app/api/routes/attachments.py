import uuid

from fastapi import APIRouter, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from app.api.deps import CookieCurrentUser, SessionDep
from app.schemas.message import AttachmentPublic

router = APIRouter(prefix="/api/attachments", tags=["attachments"])


@router.post("/{room_id}", response_model=AttachmentPublic, status_code=status.HTTP_201_CREATED)
async def upload_attachment(
    room_id: uuid.UUID,
    current_user: CookieCurrentUser,
    session: SessionDep,
    file: UploadFile,
    comment: str | None = Form(default=None),
) -> dict:
    raise HTTPException(status_code=501, detail="Not implemented")


@router.get("/{attachment_id}")
def download_attachment(attachment_id: uuid.UUID, current_user: CookieCurrentUser, session: SessionDep) -> FileResponse:
    raise HTTPException(status_code=501, detail="Not implemented")


@router.delete("/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_attachment(attachment_id: uuid.UUID, current_user: CookieCurrentUser, session: SessionDep) -> None:
    raise HTTPException(status_code=501, detail="Not implemented")
