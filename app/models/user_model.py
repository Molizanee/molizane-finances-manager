import uuid
from typing import List, TYPE_CHECKING
from typing import Optional
from sqlalchemy import UUID, ForeignKey
from sqlalchemy import String
from sqlalchemy.orm import Mapped, relationship
from sqlalchemy.orm import mapped_column
from sqlalchemy.schema import Column
from sqlalchemy.sql.sqltypes import JSON
from .base import Base

if TYPE_CHECKING:
    from .transaction_model import Transaction


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    services_authenticated: Mapped[List[str]] = mapped_column(JSON, nullable=False)
    transactions: Mapped[List["Transaction"]] = relationship(
        "Transaction", back_populates="user"
    )
