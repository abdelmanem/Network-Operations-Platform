from dataclasses import dataclass

from backend.app.domain.entities import BaseDomainEntity
from backend.app.domain.value_objects import BaseValueObject


@dataclass(frozen=True, slots=True)
class CustomerId(BaseValueObject):
    value: str

    @property
    def components(self) -> tuple[object, ...]:
        return (self.value,)


def test_domain_entity_identity() -> None:
    entity_one = BaseDomainEntity(id="abc")
    entity_two = BaseDomainEntity(id="abc")

    assert entity_one.same_identity_as(entity_two)


def test_value_object_equality_components() -> None:
    assert CustomerId("x") == CustomerId("x")
