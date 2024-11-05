from os import path, makedirs
import shutil

from fastapi import HTTPException, UploadFile
from app.core.config import settings


def save_file(file: UploadFile, storage_bucket: str, filename: str) -> str:
    storage_root = settings.STORAGE_PATH
    file_path = path.join(
        storage_bucket,
        filename,
    )
    if not path.exists(path.join(storage_root, storage_bucket)):
        makedirs(path.join(storage_root, storage_bucket), exist_ok=True)
    upfile = path.join(storage_root, file_path)

    try:
        with open(upfile, "wb") as f:
            shutil.copyfileobj(file.file, f)

    except Exception as err:
        raise HTTPException(
            detail=f"{err} encountered while uploading {file.filename}", status_code=500
        )
    finally:
        file.file.close()

    return path.join(settings.STORAGE_BASE_URL, file_path)
