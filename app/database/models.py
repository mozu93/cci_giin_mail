from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Text, ForeignKey,
    Date, UniqueConstraint, LargeBinary
)
from sqlalchemy.orm import relationship, DeclarativeBase


class Base(DeclarativeBase):
    pass


class Position(Base):
    __tablename__ = "positions"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    sort_order = Column(Integer, nullable=False, default=0)

    members = relationship("Member", back_populates="position")


class Committee(Base):
    __tablename__ = "committees"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    sort_order = Column(Integer, nullable=False, default=0)

    members = relationship("Member", back_populates="committee")


class Member(Base):
    __tablename__ = "members"
    id = Column(Integer, primary_key=True)
    member_number = Column(String, unique=True, nullable=False)
    position_id = Column(Integer, ForeignKey("positions.id"), nullable=True)
    committee_id = Column(Integer, ForeignKey("committees.id"), nullable=True)
    organization_name = Column(String, nullable=False)
    organization_kana = Column(String, default="")
    title = Column(String, default="")
    name = Column(String, nullable=False)
    name_kana = Column(String, default="")
    notes = Column(Text, default="")
    is_active = Column(Boolean, default=True)
    display_order = Column(Integer, nullable=True)
    photo_thumb = Column(LargeBinary, nullable=True)  # 64×80px JPEG
    photo_full = Column(LargeBinary, nullable=True)   # max 400×500px JPEG
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    updated_at = Column(DateTime, nullable=False,
                        default=datetime.now, onupdate=datetime.now)

    position = relationship("Position", back_populates="members")
    committee = relationship("Committee", back_populates="members")
    email_addresses = relationship(
        "EmailAddress", back_populates="member",
        order_by="EmailAddress.sort_order",
        cascade="all, delete-orphan"
    )
    history = relationship(
        "MemberHistory", back_populates="member",
        order_by="MemberHistory.changed_at.desc()",
        cascade="all, delete-orphan"
    )


class EmailAddress(Base):
    __tablename__ = "email_addresses"
    id = Column(Integer, primary_key=True)
    member_id = Column(Integer, ForeignKey("members.id"), nullable=False)
    address = Column(String, nullable=False)
    label = Column(String, default="")
    sort_order = Column(Integer, nullable=False, default=1)

    member = relationship("Member", back_populates="email_addresses")


class MemberHistory(Base):
    __tablename__ = "member_history"
    id = Column(Integer, primary_key=True)
    member_id = Column(Integer, ForeignKey("members.id"), nullable=False)
    changed_at = Column(DateTime, nullable=False, default=datetime.now)
    changed_by = Column(String, nullable=False)
    change_reason = Column(String, nullable=False)
    snapshot = Column(Text, nullable=False)  # JSON: members全フィールド＋email_addresses配列
    import_batch_id = Column(String, nullable=True)  # インポート一括操作の識別子

    member = relationship("Member", back_populates="history")


class Signature(Base):
    __tablename__ = "signatures"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    is_default = Column(Boolean, default=False)
    staff_id = Column(Integer, ForeignKey("staff.id"), nullable=True)

    templates = relationship("EmailTemplate", back_populates="signature")


class EmailTemplate(Base):
    __tablename__ = "email_templates"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    signature_id = Column(Integer, ForeignKey("signatures.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    updated_at = Column(DateTime, nullable=False,
                        default=datetime.now, onupdate=datetime.now)

    signature = relationship("Signature", back_populates="templates")


class Staff(Base):
    __tablename__ = "staff"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)

    send_jobs = relationship("SendJob", back_populates="staff")


class SendJob(Base):
    __tablename__ = "send_jobs"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    template_id = Column(Integer, ForeignKey("email_templates.id"), nullable=True)
    staff_id = Column(Integer, ForeignKey("staff.id"), nullable=True)
    status = Column(String, nullable=False, default="draft")
    total_count = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    sent_at = Column(DateTime, nullable=True)

    template = relationship("EmailTemplate")
    staff = relationship("Staff", back_populates="send_jobs")
    logs = relationship("SendLog", back_populates="job", cascade="all, delete-orphan")


class SendLog(Base):
    __tablename__ = "send_logs"
    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("send_jobs.id"), nullable=False)
    member_id = Column(Integer, ForeignKey("members.id"), nullable=True)
    to_address = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    status = Column(String, nullable=False)  # success / error / skip
    error_message = Column(Text, default="")
    sent_at = Column(DateTime, nullable=True)

    job = relationship("SendJob", back_populates="logs")
    member = relationship("Member")


class Meeting(Base):
    __tablename__ = "meetings"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    date = Column(Date, nullable=False)
    target_position_ids = Column(Text, nullable=True)  # JSON list of position IDs; NULL=全員
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    records = relationship("AttendanceRecord", back_populates="meeting",
                           cascade="all, delete-orphan")


class ReceptionLog(Base):
    __tablename__ = "reception_logs"
    id = Column(Integer, primary_key=True)
    meeting_id  = Column(Integer, ForeignKey("meetings.id"), nullable=False)
    member_id   = Column(Integer, ForeignKey("members.id"),  nullable=False)
    staff_name  = Column(String,  nullable=False)
    old_status  = Column(String,  nullable=False, default="")
    new_status  = Column(String,  nullable=False)
    changed_at  = Column(DateTime, nullable=False, default=datetime.now)
    meeting = relationship("Meeting")
    member  = relationship("Member")


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"
    id = Column(Integer, primary_key=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=False)
    member_id = Column(Integer, ForeignKey("members.id"), nullable=False)
    status = Column(String, nullable=False, default="未回答")
    actual_status = Column(String, nullable=True, default="")   # 当日受付入力
    proxy_title = Column(String, default="")
    proxy_name = Column(String, default="")
    meeting = relationship("Meeting", back_populates="records")
    member = relationship("Member")
    __table_args__ = (UniqueConstraint("meeting_id", "member_id",
                                       name="uq_meeting_member"),)
