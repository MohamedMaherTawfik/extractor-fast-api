"""SQLAlchemy type helpers shared by domain models."""

from enum import StrEnum

from sqlalchemy import CheckConstraint, Enum


def enum_type(enum_class: type[StrEnum], name: str) -> Enum:
    return Enum(
        enum_class,
        values_callable=lambda members: [member.value for member in members],
        name=name,
        native_enum=False,
        create_constraint=False,
        validate_strings=True,
    )


def enum_check(
    column_name: str,
    enum_class: type[StrEnum],
    name: str,
) -> CheckConstraint:
    values = ", ".join(repr(member.value) for member in enum_class)
    return CheckConstraint(f"{column_name} IN ({values})", name=name)
