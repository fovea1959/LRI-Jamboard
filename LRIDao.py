import logging

from LRIEntities import *

from sqlalchemy.orm import Session
from sqlalchemy import select, create_engine
from sqlalchemy.engine.result import ScalarResult

engine = create_engine('sqlite:///LRI.db', echo=False)


def team_by_number(session: Session = None, team_number: int = None) -> Team:
    stmt = select(Team).where(Team.number == team_number)
    result = session.scalars(stmt).one()
    return result


def inspector_by_id(session: Session = None, inspector_id: int = None) -> Inspector:
    stmt = select(Inspector).where(Inspector.id == inspector_id)
    result = session.scalars(stmt).one()
    return result


def inspectors_with_team_dict(session: Session = None) -> dict:
    stmt = select(Inspector)
    result = session.scalars(stmt)
    rv = {}
    for inspector in result:
        with_team = inspector.with_team
        if with_team is not None:
            teams = rv.get(inspector.with_team, None)
            if teams is None:
                rv[inspector.with_team] = teams = []
            teams.append(inspector)
    logging.info('inspectors with team dict: %s', rv)
    return rv
