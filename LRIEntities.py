import datetime
import typing

import sqlalchemy.orm.exc

from typing import List, Optional

from sqlalchemy import Integer, Text, DateTime, ForeignKey, UniqueConstraint, Boolean
from sqlalchemy.orm import DeclarativeBase, mapped_column, relationship
from sqlalchemy.orm.base import Mapped


def format_time(dt: datetime.datetime):
    rv = dt.strftime('%I:%M %p')
    if rv[0] == '0':
        rv = rv[1:]
    return rv

class Base(DeclarativeBase):
    # https://stackoverflow.com/a/11884806
    def as_dict(self, *args) -> dict:
        rv = {c.name: getattr(self, c.name) for c in self.__table__.columns}

        for name in dir(self.__class__):
            if isinstance(getattr(self.__class__, name), property):
                rv[name] = getattr(self, name)

        return rv

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

    def __repr__(self) -> str:
        # override this one if necessary
        return self._repr(**self.as_dict())


class Team(Base):
    __tablename__ = 'teams'

    STATUS_PASSED = "Passed inspection"

    number: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    school_name: Mapped[str] = mapped_column(Text)
    city: Mapped[str] = mapped_column(Text)

    seen: Mapped[bool] = mapped_column(Boolean, default=False)
    weighed: Mapped[bool] = mapped_column(Boolean, default=False)
    partially_inspected: Mapped[bool] = mapped_column(Boolean, default=False)
    passed_inspection: Mapped[bool] = mapped_column(Boolean, default=False)

    pit_location: Mapped[str] = mapped_column(Text, default='')

    @property
    def status(self) -> str:
        rv = []
        if self.passed_inspection:
            rv.append(self.STATUS_PASSED)
        else:
            if self.weighed:
                rv.append('Weighed')
            if self.partially_inspected:
                rv.append('Partially inspected')
        return ', '.join(rv)

    @property
    def present(self) -> bool:
        return self.seen or self.weighed or self.partially_inspected or self.passed_inspection

    def as_dict(self, team_to_inspector_dict: dict = None) -> dict:
        rv = super().as_dict()
        inspector_names = ''
        if team_to_inspector_dict is not None:
            inspector_names = ', '.join([i.name for i in team_to_inspector_dict.get(self.number, [])])
        rv['inspector_names'] = inspector_names
        return rv


class Inspector(Base):
    __tablename__ = 'inspectors'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    lri: Mapped[bool] = mapped_column()
    status: Mapped[str] = mapped_column(Text)
    with_team: Mapped[Optional[int]] = mapped_column(Integer)
    when: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)

    STATUS_INSPECTION_MANAGER = "Inspection Manager"
    STATUS_AVAILABLE = "Available"
    STATUS_WITH_TEAM = "With team"
    STATUS_ON_BREAK = "On break"
    STATUS_ON_FIELD = "On field"
    STATUS_GONE = "Gone"

    @property
    def status_text(self) -> str:
        rv = self.status
        if self.with_team is not None:
            rv = rv + f" {self.with_team}"
        if self.when is not None:
            rv = rv + " since " + format_time(self.when)
            seconds = self.how_long.total_seconds()
            if seconds >= (20 * 60):
                # https://stackoverflow.com/a/539360
                hours, remainder = divmod(seconds + 30, 3600)  # "+ 30" = round to minute
                minutes, seconds = divmod(remainder, 60)
                if hours < 1:
                    ts = '{} m'.format(int(minutes))
                else:
                    ts = '{} h, {} m'.format(int(hours), int(minutes))
                rv = rv + " (" + ts + ")"

        return rv

    @property
    def how_long(self) -> Optional[datetime.timedelta]:
        if self.when is None:
            return None
        return datetime.datetime.now() - self.when

    @property
    def sort_priority(self) -> int:
        if self.lri:
            return 10
        if self.status == self.STATUS_INSPECTION_MANAGER:
            return 0
        elif self.status == self.STATUS_AVAILABLE:
            return 1000
        elif self.status == self.STATUS_WITH_TEAM:
            return 10000000 - int(self.how_long.total_seconds())
        elif self.status in (self.STATUS_ON_BREAK, self.STATUS_ON_FIELD):
            return 20000000 - int(self.how_long.total_seconds())
        else:
            return 99999999

    @property
    def hide(self) -> bool:
        return self.status in (self.STATUS_GONE, ) and not self.lri