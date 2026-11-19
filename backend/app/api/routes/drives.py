import uuid

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile, status

from app.api.deps import get_drive_service, require_student
from app.core.errors import BadRequestError
from app.domain.extraction.models import DriveInfo
from app.models.user import User
from app.schemas.drive import (
    DriveDetail,
    DriveList,
    DriveStatus,
    EligibilityStatus,
    StatusUpdate,
    UploadResponse,
)
from app.services.drive_service import DriveService

router = APIRouter(prefix="/drives", tags=["drives"])


@router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
def upload(
    file: UploadFile | None = File(default=None, description="PDF, DOCX or XLSX, max 10 MB"),
    text: str | None = Form(default=None, description="Or paste the notice text"),
    user: User = Depends(require_student),
    drives: DriveService = Depends(get_drive_service),
) -> UploadResponse:
    if file is not None and file.filename:
        # Read one byte past the limit so oversize files are rejected without buffering more.
        content = file.file.read(drives.settings.max_upload_bytes + 1)
        links = drives.upload_file(user, file.filename, content)
    elif text is not None and text.strip():
        links = drives.upload_text(user, text)
    else:
        raise BadRequestError("VALIDATION_ERROR", "Send a file or paste the notice text", 422)
    return UploadResponse(drives=[drives.to_detail(link) for link in links])


@router.get("", response_model=DriveList)
def list_drives(
    status: DriveStatus | None = None,
    eligibility: EligibilityStatus | None = None,
    closing_soon: bool | None = None,
    user: User = Depends(require_student),
    drives: DriveService = Depends(get_drive_service),
) -> DriveList:
    links = drives.list_for(user, status, eligibility, closing_soon)
    return DriveList(drives=[drives.to_detail(link) for link in links])


@router.get("/{drive_id}", response_model=DriveDetail)
def get_drive(
    drive_id: uuid.UUID,
    user: User = Depends(require_student),
    drives: DriveService = Depends(get_drive_service),
) -> DriveDetail:
    return drives.to_detail(drives.get(user, drive_id))


@router.patch("/{drive_id}", response_model=DriveDetail)
def edit_drive(
    drive_id: uuid.UUID,
    body: DriveInfo,
    user: User = Depends(require_student),
    drives: DriveService = Depends(get_drive_service),
) -> DriveDetail:
    return drives.to_detail(drives.edit(user, drive_id, body))


@router.patch("/{drive_id}/status", response_model=DriveDetail)
def update_status(
    drive_id: uuid.UUID,
    body: StatusUpdate,
    user: User = Depends(require_student),
    drives: DriveService = Depends(get_drive_service),
) -> DriveDetail:
    return drives.to_detail(drives.update_status(user, drive_id, body.status))


@router.delete("/{drive_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_drive(
    drive_id: uuid.UUID,
    user: User = Depends(require_student),
    drives: DriveService = Depends(get_drive_service),
) -> Response:
    drives.delete(user, drive_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
