from uuid import UUID

from backend.app.models.base import BaseModel
from backend.app.models.mixins import (
    RepresentationMixin,
    TableNameMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Mapped, mapped_column, sessionmaker


class SampleModel(
    TableNameMixin,
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    RepresentationMixin,
    BaseModel,
):
    name: Mapped[str] = mapped_column()


def test_mixins_support_orm_persistence() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    BaseModel.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, future=True)

    with session_factory() as session:
        item = SampleModel(name="demo")
        session.add(item)
        session.flush()

        assert item.created_at is not None
        assert item.updated_at is not None
        assert item.created_at.tzinfo is not None
        assert item.updated_at.tzinfo is not None
        session.commit()

        loaded = session.scalars(select(SampleModel)).one()

    assert SampleModel.__tablename__ == "samplemodel"
    assert isinstance(loaded.id, UUID)
    assert loaded.to_dict()["name"] == "demo"
