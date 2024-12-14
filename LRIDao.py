from LRIEntities import *

from sqlalchemy.orm import Session
from sqlalchemy import select, create_engine
from sqlalchemy.engine.result import ScalarResult

engine = create_engine('sqlite:///LRI.db', echo=False)


def team_by_number(session: Session = None, team_number: int = None) -> Team:
    stmt = select(Team).where(Team.team_number == team_number)
    result = session.scalars(stmt).one()
    return result
