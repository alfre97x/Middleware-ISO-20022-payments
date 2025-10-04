from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import (
    Column,
    String,
    DateTime,
    Numeric,
    Index,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.types import TypeDecorator, CHAR

from .db import Base


class GUID(TypeDecorator):
    """
    Platform-independent GUID/UUID type.

    Uses PostgreSQL UUID when available, otherwise stores as CHAR(36) for SQLite/others.
    """
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "postgresql":
            if isinstance(value, uuid.UUID):
                return value
            return uuid.UUID(str(value))
        # store as string
        if isinstance(value, uuid.UUID):
            return str(value)
        return str(uuid.UUID(str(value)))

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "postgresql":
            return value  # already UUID
        return uuid.UUID(value)


class Receipt(Base):
    __tablename__ = "receipts"

    id = Column(GUID, primary_key=True, default=uuid.uuid4, nullable=False)

    reference = Column(String, nullable=False, unique=True)
    tip_tx_hash = Column(String, nullable=False)
    chain = Column(String, nullable=False)  # "coston2" | "flare"

    amount = Column(Numeric(38, 18), nullable=False)
    currency = Column(String, nullable=False)  # "FLR" for PoC

    sender_wallet = Column(String, nullable=False)
    receiver_wallet = Column(String, nullable=False)

    status = Column(String, nullable=False, index=True)  # pending/anchored/failed

    bundle_hash = Column(String, nullable=True)  # 0x-prefixed sha256 of zip
    flare_txid = Column(String, nullable=True)

    xml_path = Column(String, nullable=True)
    bundle_path = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    anchored_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("chain", "tip_tx_hash", name="uq_chain_tip"),
        Index("ix_receipts_status", "status"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Receipt id={self.id} status={self.status} tip={self.tip_tx_hash}>"
