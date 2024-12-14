import datetime
import typing

import sqlalchemy.orm.exc

from typing import List, Optional

from sqlalchemy import Integer, Text, DateTime, ForeignKey, UniqueConstraint, Boolean
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

    def __repr__(self):
        # override this one if necessary
        return self._repr(**self.as_dict())


class Team(Base):
    __tablename__ = 'teams'

    STATUS_WEIGHED = "Weighed"
    STATUS_PASSED = "Passed Inspection"
    STATUS_NONE = ""

    team_number: Mapped[int] = mapped_column(Integer, primary_key=True)
    team_name: Mapped[str] = mapped_column(Text)
    school_name: Mapped[str] = mapped_column(Text)
    city: Mapped[str] = mapped_column(Text)

    weighed: Mapped[bool] = mapped_column(Boolean)
    inspected: Mapped[bool] = mapped_column(Boolean)

    @property
    def status(self):
        rv = self.STATUS_NONE
        if self.weighed:
            if self.inspected:
                rv = self.STATUS_PASSED
            else:
                rv = self.STATUS_WEIGHED
        return rv

    def as_dict(self):
        rv = super().as_dict()
        rv['status'] = self.status
        return rv


class Inspector(Base):
    __tablename__ = 'inspectors'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    with_team: Mapped[Optional[int]] = mapped_column(Integer)
    when: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)

    @property
    def status_text(self):
        rv = self.status
        if self.with_team is not None:
            rv = rv + f" with {self.with_team}"
        if self.when is not None:
            rv = rv + f" since {self.when} ({self.how_long})"
        return rv

    @property
    def how_long(self):
        if self.when is None:
            return None
        return datetime.datetime.now() - self.when

    def as_dict(self):
        rv = super().as_dict()
        rv['status_text'] = self.status_text
        rv['how_long'] = self.how_long
        return rv
