# app/services/photo_service.py
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtCore import Qt, QByteArray, QBuffer, QIODeviceBase

_THUMB_W, _THUMB_H = 64, 80
_FULL_W,  _FULL_H  = 400, 500


def _to_jpeg_bytes(image: QImage, max_w: int, max_h: int) -> bytes:
    scaled = image.scaled(max_w, max_h,
                          Qt.AspectRatioMode.KeepAspectRatio,
                          Qt.TransformationMode.SmoothTransformation)
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODeviceBase.OpenModeFlag.WriteOnly)
    scaled.save(buf, "JPEG", 85)
    buf.close()
    return bytes(ba)


def save_photo(session, member_id: int, image_path: str) -> None:
    img = QImage(image_path)
    if img.isNull():
        raise ValueError(f"画像を読み込めませんでした: {image_path}")
    from app.database.models import Member
    m = session.get(Member, member_id)
    if not m:
        return
    m.photo_thumb = _to_jpeg_bytes(img, _THUMB_W, _THUMB_H)
    m.photo_full  = _to_jpeg_bytes(img, _FULL_W,  _FULL_H)
    session.commit()


def delete_photo(session, member_id: int) -> None:
    from app.database.models import Member
    m = session.get(Member, member_id)
    if m:
        m.photo_thumb = None
        m.photo_full  = None
        session.commit()


def bytes_to_pixmap(data: bytes | None) -> QPixmap | None:
    if not data:
        return None
    img = QImage()
    img.loadFromData(data)
    return None if img.isNull() else QPixmap.fromImage(img)
