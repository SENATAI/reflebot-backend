import uuid
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from reflebot.core.db import Base
from reflebot.core.models import TimestampMixin


class File(Base, TimestampMixin):
    """Модель файла в системе"""

    __tablename__ = "files"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    path: Mapped[str] = mapped_column(
        sa.String(256), unique=True, nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(sa.String(256), nullable=False)
    content_type: Mapped[str] = mapped_column(sa.String(256), nullable=False)
    size: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
