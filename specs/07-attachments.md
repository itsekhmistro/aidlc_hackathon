# TASK-07: File & Image Attachments

**Agent:** `/backend` + `/frontend`  
**Phase:** 2 — Features  
**Depends on:** 06-messaging  
**Parallel with:** 08-notifications

---

## Overview

Files stored on local filesystem under `UPLOAD_DIR` (Docker volume). Access control enforced at download time — membership is re-checked on every GET. Max 20 MB for files, 3 MB for images.

---

## Backend

### Routes (`backend/app/api/routes/attachments.py`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/attachments/{room_id}` | Upload file, returns attachment object |
| GET | `/api/attachments/{attachment_id}` | Download (membership verified at request time) |
| DELETE | `/api/attachments/{attachment_id}` | Delete own attachment (or room admin) |

### Upload Endpoint

```python
@router.post("/attachments/{room_id}")
async def upload_attachment(
    room_id: UUID,
    file: UploadFile,
    message_id: UUID | None = Form(None),   # attach to existing draft message
    comment: str | None = Form(None),
    current_user: User = Depends(get_current_user)
):
    # 1. Verify membership
    # 2. Check size limits (image: 3 MB, other: 20 MB)
    # 3. Generate stored_path = UPLOAD_DIR/{room_id}/{uuid4()}/{original_filename}
    # 4. Write file to disk (streaming, avoid loading full file into memory)
    # 5. Insert Attachment record
    # 6. Return attachment schema
```

### Download Endpoint

```python
@router.get("/attachments/{attachment_id}")
async def download_attachment(attachment_id: UUID, current_user: User = ...):
    attachment = get_or_404(attachment_id)
    # Re-check membership at download time
    if not is_member(current_user.id, attachment.message.room_id):
        raise HTTPException(403)
    return FileResponse(
        path=attachment.stored_path,
        filename=attachment.original_filename,
        media_type=attachment.mime_type
    )
```

### Storage Path Convention

```
/uploads/
  {room_id}/
    {attachment_id}/
      {original_filename}
```

### Cleanup Hooks

- Room deleted → `rmtree(UPLOAD_DIR/{room_id}/)`
- Attachment deleted → `unlink(stored_path)`

### Size Validation

- Detect content type from `file.content_type` (also validate with `python-magic` if available)
- Images: `image/*` → max 3 MB
- All others → max 20 MB
- Return 413 if exceeded

---

## Frontend

### Upload UI

#### Attach Button

- `<input type="file">` hidden, triggered by button click
- Supports multiple files per message

#### Paste Support (`frontend/src/hooks/usePasteUpload.ts`)

```typescript
document.addEventListener('paste', (e) => {
  const files = e.clipboardData?.files;
  if (files?.length) handleFiles(Array.from(files));
});
```

#### Upload Flow

1. User selects/pastes file(s)
2. Show preview row in input area: filename + size + optional comment input + remove button
3. On send: POST to `/api/attachments/{room_id}` then include `attachment_id` in message POST
4. Show upload progress bar (XHR with `onprogress`)

### Attachment Display in Message

#### Image attachments
```
┌──────────────────────────────┐
│  [thumbnail 200px wide]      │
│  photo.jpg · 1.2 MB          │
│  comment: team photo          │
└──────────────────────────────┘
```
Click → opens full-size lightbox

#### File attachments
```
┌──────────────────────────────────┐
│  📄  spec-v3.pdf   420 KB  [↓]  │
│  comment: latest requirements    │
└──────────────────────────────────┘
```
Click download icon → GET `/api/attachments/{id}` (browser handles as download)

### Access Enforcement

- If user loses room access while viewing → subsequent attachment requests return 403 → show "No longer accessible" placeholder

---

## Acceptance Criteria

- [x] Upload image ≤ 3 MB → stored, visible in message, downloadable
- [x] Upload file ≤ 20 MB → stored, downloadable
- [x] Upload over size limit → 413, error shown to user
- [x] Original filename preserved
- [x] Optional comment saved + displayed
- [x] Paste from clipboard uploads file
- [x] User banned from room → existing attachment GET returns 403
- [x] Room deleted → all attachment files removed from disk
- [x] Download endpoint verifies membership on every request (not just upload time)

