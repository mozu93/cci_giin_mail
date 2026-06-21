from sqlalchemy.orm import Session
from app.database.models import Signature


def create_signature(session: Session, name: str, body: str,
                     is_default: bool = False) -> Signature:
    sig = Signature(name=name, body=body, is_default=is_default)
    session.add(sig)
    session.commit()
    return sig


def get_signatures(session: Session) -> list[Signature]:
    return session.query(Signature).order_by(Signature.name).all()


def get_default_signature(session: Session) -> Signature | None:
    return session.query(Signature).filter_by(is_default=True).first()


def set_default(session: Session, sig_id: int) -> None:
    session.query(Signature).update({"is_default": False})
    sig = session.get(Signature, sig_id)
    if sig:
        sig.is_default = True
    session.commit()


def update_signature(session: Session, sig_id: int, **kwargs) -> Signature:
    sig = session.get(Signature, sig_id)
    if sig is None:
        raise ValueError(f"署名ID {sig_id} が見つかりません")
    for k, v in kwargs.items():
        setattr(sig, k, v)
    session.commit()
    return sig


def delete_signature(session: Session, sig_id: int) -> None:
    sig = session.get(Signature, sig_id)
    if sig:
        session.delete(sig)
        session.commit()
