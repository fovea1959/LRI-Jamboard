from LRIEntities import *

from sqlalchemy.orm import Session
from sqlalchemy import select, create_engine
from sqlalchemy.engine.result import ScalarResult

engine = create_engine('sqlite:///LRI.db', echo=False)


def team_by_number(session: Session = None, team_number: int = None) -> ScalarResultTeam:
    stmt = select(Team).where(Team.number == team_number)
    result = session.scalars(stmt).one()
    return result


def inspector_by_id(session: Session = None, inspector_id: int = None) -> Inspector:
    stmt = select(Inspector).where(Inspector.id == inspector_id)
    result = session.scalars(stmt).one()
    return result
