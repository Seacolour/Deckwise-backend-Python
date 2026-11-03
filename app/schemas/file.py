"""Web-compatible upload responses and bounded parsed-text reads."""

from pydantic import BaseModel


class FileUploadItemDTO(BaseModel):
    sourceFileId: str
    fileId: str
    fileName: str
    fileSize: int
    sizeBytes: int
    mimeType: str
    objectKey: str
    storageChannel: str = "private"
    visibility: str = "private"
    cacheKey: str
    totalFragments: int


class FileUploadBatchDTO(BaseModel):
    batchId: str
    projectId: str
    totalCount: int
    files: list[FileUploadItemDTO]


class PrivateObjectAccessUrlDTO(BaseModel):
    accessUrl: str


class FileFragmentDTO(BaseModel):
    index: int
    content: str


class FileContentPageDTO(BaseModel):
    fileId: str
    cacheKey: str
    fileName: str
    startIndex: int
    totalFragments: int
    fragments: list[FileFragmentDTO]
    hasMore: bool
