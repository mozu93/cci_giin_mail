from sqlalchemy.orm import Session
from app.database.models import EmailTemplate


def create_template(session: Session, name: str, subject: str, body: str,
                    signature_id: int | None = None) -> EmailTemplate:
    t = EmailTemplate(name=name, subject=subject, body=body,
                      signature_id=signature_id)
    session.add(t)
    session.commit()
    return t


def get_template(session: Session, template_id: int) -> EmailTemplate | None:
    return session.get(EmailTemplate, template_id)


def get_templates(session: Session) -> list[EmailTemplate]:
    return session.query(EmailTemplate).order_by(EmailTemplate.name).all()


def update_template(session: Session, template_id: int, **kwargs) -> EmailTemplate:
    t = session.get(EmailTemplate, template_id)
    if t is None:
        raise ValueError(f"テンプレートID {template_id} が見つかりません")
    for k, v in kwargs.items():
        setattr(t, k, v)
    session.commit()
    return t


def delete_template(session: Session, template_id: int) -> None:
    t = session.get(EmailTemplate, template_id)
    if t:
        session.delete(t)
        session.commit()
