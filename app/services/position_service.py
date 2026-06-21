from sqlalchemy.orm import Session
from app.database.models import Position


def create_position(session: Session, name: str, sort_order: int) -> Position:
    pos = Position(name=name, sort_order=sort_order)
    session.add(pos)
    session.commit()
    return pos


def get_positions(session: Session) -> list[Position]:
    return session.query(Position).order_by(Position.sort_order).all()


def update_position(session: Session, pos_id: int, **kwargs) -> Position:
    pos = session.get(Position, pos_id)
    if pos is None:
        raise ValueError(f"役職ID {pos_id} が見つかりません")
    for k, v in kwargs.items():
        setattr(pos, k, v)
    session.commit()
    return pos


def delete_position(session: Session, pos_id: int) -> None:
    pos = session.get(Position, pos_id)
    if pos:
        session.delete(pos)
        session.commit()
