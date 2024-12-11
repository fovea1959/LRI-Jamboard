import datetime
import typing

import sqlalchemy.orm.exc

from typing import List, Optional

from sqlalchemy import Integer, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, mapped_column, relationship
from sqlalchemy.orm.base import Mapped


class Base(DeclarativeBase):
    # https://stackoverflow.com/a/11884806
    def as_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}

    def _repr(self, **fields: typing.Dict[str, typing.Any]) -> str:
        # Helper for __repr__
        field_strings = []
        at_least_one_attached_attribute = False
        for key, field in fields.items():
            try:
                field_strings.append(f'{key}={field!r}')
            except sqlalchemy.orm.exc.DetachedInstanceError:
                field_strings.append(f'{key}=DetachedInstanceError')
            else:
                at_least_one_attached_attribute = True
        if at_least_one_attached_attribute:
            return f"<{self.__class__.__name__}({','.join(field_strings)})>"
        return f"<{self.__class__.__name__} {id(self)}>"


class Team(Base):
    __tablename__ = 'teams'

    team_number: Mapped[int] = mapped_column(Integer, primary_key=True)
    team_name: Mapped[str] = mapped_column(Text)
    school_name: Mapped[str] = mapped_column(Text)
    city: Mapped[str] = mapped_column(Text)