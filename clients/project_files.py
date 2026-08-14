import re
import unicodedata
import uuid
import zipfile
from dataclasses import dataclass

from cloudinary import CloudinaryResource
from cloudinary.uploader import destroy, upload_resource
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction

from .models import ProjectFile


@dataclass(frozen=True)
class FileRule:
    mime_types: frozenset[str]
    resource_type: str
    delivery_type: str
    preview_kind: str | None = None
    provider_formats: frozenset[str] = frozenset()


IMAGE_AUTHENTICATED = (
    ProjectFile.ProviderResourceType.IMAGE,
    ProjectFile.ProviderDeliveryType.AUTHENTICATED,
)
VIDEO_AUTHENTICATED = (
    ProjectFile.ProviderResourceType.VIDEO,
    ProjectFile.ProviderDeliveryType.AUTHENTICATED,
)
RAW_PRIVATE = (
    ProjectFile.ProviderResourceType.RAW,
    ProjectFile.ProviderDeliveryType.PRIVATE,
)


def rule(mime_types, storage, preview_kind=None, provider_formats=()):
    return FileRule(
        mime_types=frozenset(mime_types),
        resource_type=storage[0],
        delivery_type=storage[1],
        preview_kind=preview_kind,
        provider_formats=frozenset(provider_formats),
    )


FILE_RULES = {
    "jpg": rule({"image/jpeg"}, IMAGE_AUTHENTICATED, "image", {"jpg", "jpeg"}),
    "jpeg": rule({"image/jpeg"}, IMAGE_AUTHENTICATED, "image", {"jpg", "jpeg"}),
    "png": rule({"image/png"}, IMAGE_AUTHENTICATED, "image", {"png"}),
    "webp": rule({"image/webp"}, IMAGE_AUTHENTICATED, "image", {"webp"}),
    "tif": rule({"image/tiff"}, IMAGE_AUTHENTICATED, None, {"tif", "tiff"}),
    "tiff": rule({"image/tiff"}, IMAGE_AUTHENTICATED, None, {"tif", "tiff"}),
    "svg": rule({"image/svg+xml"}, RAW_PRIVATE, None, {"svg"}),
    "pdf": rule({"application/pdf"}, IMAGE_AUTHENTICATED, "pdf", {"pdf"}),
    "mp4": rule({"video/mp4"}, VIDEO_AUTHENTICATED, "video", {"mp4"}),
    "mov": rule({"video/quicktime"}, VIDEO_AUTHENTICATED, None, {"mov"}),
    "webm": rule({"video/webm"}, VIDEO_AUTHENTICATED, "video", {"webm"}),
    "wav": rule({"audio/wav", "audio/x-wav"}, VIDEO_AUTHENTICATED, "audio", {"wav"}),
    "mp3": rule({"audio/mpeg"}, VIDEO_AUTHENTICATED, "audio", {"mp3"}),
    "m4a": rule({"audio/mp4", "audio/x-m4a"}, VIDEO_AUTHENTICATED, None, {"m4a", "mp4"}),
    "doc": rule({"application/msword"}, RAW_PRIVATE, None, {"doc"}),
    "docx": rule(
        {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
        RAW_PRIVATE,
        None,
        {"docx"},
    ),
    "ppt": rule({"application/vnd.ms-powerpoint"}, RAW_PRIVATE, None, {"ppt"}),
    "pptx": rule(
        {"application/vnd.openxmlformats-officedocument.presentationml.presentation"},
        RAW_PRIVATE,
        None,
        {"pptx"},
    ),
    "xls": rule({"application/vnd.ms-excel"}, RAW_PRIVATE, None, {"xls"}),
    "xlsx": rule(
        {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
        RAW_PRIVATE,
        None,
        {"xlsx"},
    ),
    "txt": rule({"text/plain"}, RAW_PRIVATE, None, {"txt"}),
    "csv": rule({"text/csv", "application/csv"}, RAW_PRIVATE, None, {"csv"}),
    "zip": rule(
        {"application/zip", "application/x-zip-compressed"},
        RAW_PRIVATE,
        None,
        {"zip"},
    ),
}


@dataclass(frozen=True)
class InspectedProjectFile:
    filename: str
    extension: str
    content_type: str
    size_bytes: int
    rule: FileRule


@dataclass(frozen=True)
class StoredProjectFile:
    resource: object
    asset_id: str
    public_id: str
    resource_type: str
    delivery_type: str
    provider_format: str
    version: int
    size_bytes: int


def _validation_error(message):
    raise ValidationError({"file": message})


def normalize_original_filename(filename):
    if not filename:
        _validation_error("A filename is required.")
    normalized = unicodedata.normalize("NFC", str(filename).replace("\\", "/"))
    normalized = normalized.rsplit("/", 1)[-1]
    normalized = "".join(
        character
        for character in normalized
        if unicodedata.category(character) not in {"Cc", "Cf"}
    ).strip()
    if not normalized or normalized in {".", ".."}:
        _validation_error("A valid filename is required.")
    if len(normalized) > 255:
        _validation_error("The filename must be 255 characters or fewer.")
    return normalized


def normalize_display_name(display_name):
    if not display_name:
        return ""
    normalized = unicodedata.normalize("NFC", str(display_name))
    normalized = "".join(
        character
        for character in normalized
        if unicodedata.category(character) not in {"Cc", "Cf"}
    ).strip()
    if len(normalized) > 255:
        raise ValidationError({"display_name": "The display name must be 255 characters or fewer."})
    return normalized


def _read_head(uploaded_file, length=65536):
    uploaded_file.seek(0)
    head = uploaded_file.read(length)
    uploaded_file.seek(0)
    return head


def _zip_kind(uploaded_file):
    uploaded_file.seek(0)
    try:
        with zipfile.ZipFile(uploaded_file) as archive:
            names = {name.lower() for name in archive.namelist()}
    except (OSError, zipfile.BadZipFile, zipfile.LargeZipFile):
        uploaded_file.seek(0)
        return None
    finally:
        uploaded_file.seek(0)

    if "[content_types].xml" in names:
        if any(name.startswith("word/") for name in names):
            return "docx"
        if any(name.startswith("ppt/") for name in names):
            return "pptx"
        if any(name.startswith("xl/") for name in names):
            return "xlsx"
    return "zip"


def _has_valid_signature(uploaded_file, extension):
    head = _read_head(uploaded_file)
    if extension in {"jpg", "jpeg"}:
        return head.startswith(b"\xff\xd8\xff")
    if extension == "png":
        return head.startswith(b"\x89PNG\r\n\x1a\n")
    if extension == "webp":
        return len(head) >= 12 and head[:4] == b"RIFF" and head[8:12] == b"WEBP"
    if extension in {"tif", "tiff"}:
        return head.startswith((b"II*\x00", b"MM\x00*"))
    if extension == "svg":
        lowered = head.lstrip(b"\xef\xbb\xbf\x00\t\r\n ").lower()
        return (
            b"<!doctype" not in lowered
            and b"<!entity" not in lowered
            and re.search(br"<svg(?:\s|>)", lowered[:8192]) is not None
        )
    if extension == "pdf":
        return head.startswith(b"%PDF-")
    if extension in {"mp4", "mov", "m4a"}:
        return len(head) >= 12 and head[4:8] == b"ftyp"
    if extension == "webm":
        return head.startswith(b"\x1aE\xdf\xa3") and b"webm" in head[:4096].lower()
    if extension == "wav":
        return len(head) >= 12 and head[:4] == b"RIFF" and head[8:12] == b"WAVE"
    if extension == "mp3":
        return head.startswith(b"ID3") or (
            len(head) >= 2 and head[0] == 0xFF and head[1] & 0xE0 == 0xE0
        )
    if extension in {"doc", "ppt", "xls"}:
        return head.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")
    if extension in {"docx", "pptx", "xlsx", "zip"}:
        return _zip_kind(uploaded_file) == extension
    if extension in {"txt", "csv"}:
        if b"\x00" in head:
            return False
        try:
            head.decode("utf-8")
        except UnicodeDecodeError:
            return False
        return True
    return False


def inspect_proxy_upload(uploaded_file):
    filename = normalize_original_filename(getattr(uploaded_file, "name", ""))
    if "." not in filename:
        _validation_error("The file must have a supported extension.")
    extension = filename.rsplit(".", 1)[-1].lower()
    selected_rule = FILE_RULES.get(extension)
    if selected_rule is None:
        _validation_error(f"Files with the .{extension} extension are not supported.")

    size_bytes = int(getattr(uploaded_file, "size", 0) or 0)
    if size_bytes <= 0:
        _validation_error("The file is empty.")
    proxy_limit = int(settings.PROJECT_FILE_PROXY_UPLOAD_MAX_BYTES)
    if size_bytes > proxy_limit:
        _validation_error(
            "This file is too large for the temporary server upload path. "
            "Use a smaller file until direct large-file uploads are available."
        )

    content_type = str(getattr(uploaded_file, "content_type", "") or "")
    content_type = content_type.split(";", 1)[0].strip().lower()
    if content_type not in selected_rule.mime_types:
        _validation_error(
            f"The declared content type does not match the .{extension} file extension."
        )
    if not _has_valid_signature(uploaded_file, extension):
        _validation_error(
            f"The file contents do not match the .{extension} file extension."
        )
    uploaded_file.seek(0)
    return InspectedProjectFile(
        filename=filename,
        extension=extension,
        content_type=content_type,
        size_bytes=size_bytes,
        rule=selected_rule,
    )


class CloudinaryProjectFileProvider:
    name = ProjectFile.StorageProvider.CLOUDINARY

    def upload(self, uploaded_file, inspected_file, project_id):
        generated_id = f"projects/{project_id}/{uuid.uuid4().hex}"
        if inspected_file.rule.resource_type == ProjectFile.ProviderResourceType.RAW:
            generated_id = f"{generated_id}.{inspected_file.extension}"
        uploaded_file.seek(0)
        resource = upload_resource(
            uploaded_file,
            public_id=generated_id,
            resource_type=inspected_file.rule.resource_type,
            type=inspected_file.rule.delivery_type,
            overwrite=False,
            use_filename=False,
            unique_filename=False,
        )
        try:
            return self._verified_resource(resource, inspected_file, generated_id)
        except ValidationError:
            try:
                destroy(
                    resource.public_id,
                    resource_type=resource.resource_type,
                    type=resource.type,
                    invalidate=True,
                )
            except Exception:
                pass
            raise

    def _verified_resource(self, resource, inspected_file, expected_public_id):
        metadata = resource.metadata or {}
        resource_type = resource.resource_type or metadata.get("resource_type")
        delivery_type = resource.type or metadata.get("type")
        public_id = resource.public_id or metadata.get("public_id")
        provider_format = (resource.format or metadata.get("format") or "").lower()
        asset_id = metadata.get("asset_id")
        version = resource.version or metadata.get("version")
        provider_size = metadata.get("bytes")

        if resource_type != inspected_file.rule.resource_type:
            _validation_error("The storage provider returned an unexpected resource type.")
        if delivery_type != inspected_file.rule.delivery_type:
            _validation_error("The storage provider returned an unexpected delivery type.")
        if public_id != expected_public_id:
            _validation_error("The storage provider returned an unexpected asset identifier.")
        if not asset_id or version is None or provider_size is None:
            _validation_error("The storage provider response is missing required asset metadata.")
        if int(provider_size) != inspected_file.size_bytes:
            _validation_error("The storage provider returned an unexpected file size.")
        if provider_format and provider_format not in inspected_file.rule.provider_formats:
            _validation_error("The storage provider returned an unexpected file format.")
        if resource_type != ProjectFile.ProviderResourceType.RAW and not provider_format:
            _validation_error("The storage provider response is missing the asset format.")
        try:
            version = int(version)
        except (TypeError, ValueError):
            _validation_error("The storage provider returned an invalid asset version.")

        stored_resource = resource
        if resource_type == ProjectFile.ProviderResourceType.RAW:
            stored_resource = CloudinaryResource(
                public_id,
                version=version,
                format=None,
                type=delivery_type,
                resource_type=resource_type,
                metadata={**metadata, "format": None},
            )
        return StoredProjectFile(
            resource=stored_resource,
            asset_id=str(asset_id),
            public_id=public_id,
            resource_type=resource_type,
            delivery_type=delivery_type,
            provider_format=provider_format,
            version=version,
            size_bytes=int(provider_size),
        )

    def delete(self, stored_file):
        destroy(
            stored_file.public_id,
            resource_type=stored_file.resource_type,
            type=stored_file.delivery_type,
            invalidate=True,
        )


def create_project_file(
    *,
    project,
    uploaded_by,
    uploaded_file,
    category,
    display_name="",
    supersedes=None,
    provider=None,
):
    inspected_file = inspect_proxy_upload(uploaded_file)
    if category not in ProjectFile.Category.values:
        raise ValidationError({"category": "Select a valid file category."})
    if supersedes is not None:
        if supersedes.project_id != project.id:
            raise ValidationError(
                {"supersedes": "A file can only supersede a version in the same project."}
            )
        if supersedes.category != category:
            raise ValidationError(
                {"supersedes": "A file can only supersede a version in the same category."}
            )

    display_name = normalize_display_name(display_name)
    provider = provider or CloudinaryProjectFileProvider()
    stored_file = provider.upload(uploaded_file, inspected_file, project.id)
    try:
        with transaction.atomic():
            return ProjectFile.objects.create(
                project=project,
                uploaded_by=uploaded_by,
                file=stored_file.resource,
                filename=inspected_file.filename,
                display_name=display_name,
                category=category,
                content_type=inspected_file.content_type,
                extension=inspected_file.extension,
                size_bytes=stored_file.size_bytes,
                storage_provider=provider.name,
                provider_asset_id=stored_file.asset_id,
                provider_public_id=stored_file.public_id,
                provider_resource_type=stored_file.resource_type,
                provider_delivery_type=stored_file.delivery_type,
                provider_format=stored_file.provider_format,
                provider_version=stored_file.version,
                supersedes=supersedes,
            )
    except Exception:
        try:
            provider.delete(stored_file)
        except Exception:
            pass
        raise
