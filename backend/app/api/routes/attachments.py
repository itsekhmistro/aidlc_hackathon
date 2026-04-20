import uuid
import pathlib
import shutil

from fastapi import APIRouter, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlmodel import select

from app.api.deps import CookieCurrentUser, SessionDep
from app.core.config import settings
from app.models.message import Attachment
from app.models.room import RoomMember
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
    membership = session.exec(
        select(RoomMember).where(RoomMember.room_id == room_id, RoomMember.user_id == current_user.id)
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="Not a member of this room")

    content = await file.read()
    if len(content) > settings.MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="File too large")

    attachment_id = uuid.uuid4()
    safe_name = pathlib.Path(file.filename or "file").name
    dest_dir = pathlib.Path(settings.UPLOAD_DIR) / str(attachment_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / safe_name
    dest_path.write_bytes(content)

    att = Attachment(
        id=attachment_id,
        room_id=room_id,
        message_id=None,
        original_filename=safe_name,
        stored_path=str(dest_path),
        mime_type=file.content_type or "application/octet-stream",
        size_bytes=len(content),
        comment=comment,
        uploaded_by_id=current_user.id,
    )
    session.add(att)
    session.commit()
    session.refresh(att)

    return AttachmentPublic(
        id=att.id,
        original_filename=att.original_filename,
        mime_type=att.mime_type,
        size_bytes=att.size_bytes,
        comment=att.comment,
        created_at=att.created_at,
    )


@router.get("/{attachment_id}")
def download_attachment(
    attachment_id: uuid.UUID,
    current_user: CookieCurrentUser,
    session: SessionDep,
) -> FileResponse:
    att = session.get(Attachment, attachment_id)
    if not att:
        raise HTTPException(status_code=404, detail="Attachment not found")
    is_uploader = att.uploaded_by_id == current_user.id
    is_member = session.exec(
        select(RoomMember).where(RoomMember.room_id == att.room_id, RoomMember.user_id == current_user.id)
    ).first() is not None
    if not is_uploader and not is_member:
        raise HTTPException(status_code=403, detail="Access denied")
    if not pathlib.Path(att.stored_path).exists():
        raise HTTPException(status_code=404, detail="File not found on disk")
    return FileResponse(att.stored_path, filename=att.original_filename, media_type=att.mime_type)


@router.delete("/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_attachment(
    attachment_id: uuid.UUID,
    current_user: CookieCurrentUser,
    session: SessionDep,
) -> None:
    att = session.get(Attachment, attachment_id)
    if not att:
        raise HTTPException(status_code=404, detail="Attachment not found")
    if att.uploaded_by_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the uploader can delete this attachment")
    try:
        shutil.rmtree(pathlib.Path(att.stored_path).parent, ignore_errors=True)
    except Exception:
        pass
    session.delete(att)
    session.commit()
