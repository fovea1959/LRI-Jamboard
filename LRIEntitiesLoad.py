import datetime
import json
import os
import sys

from sqlalchemy.orm import Session

import LRIDao as Dao
from LRIEntities import *


def main(argv):
    try:
        os.remove('LRI.db')
    except FileNotFoundError:
        pass
    Base.metadata.create_all(Dao.engine)

    with open('2025misjo_teams.json', 'r') as f:
        blue_alliance = json.load(f)
    print('# of teams:', len(blue_alliance))

    with (Session(Dao.engine) as session):
        for team_dict in blue_alliance:  # type: dict
            team_number = team_dict['team_number']
            team = Team(
                number=team_number,
                name=team_dict['nickname'],
                school_name=team_dict['school_name'],
                city=team_dict['city'],
                seen=team_number in (2959,),
                weighed=team_number in (74, 1940, 3620),
                partially_inspected=team_number in (1940, ),
                passed_inspection=team_number in (3620, ),
            )
            session.add(team)
        session.commit()

        n = [
            ('Tearesa W', Inspector.STATUS_AVAILABLE, None),
            ('Doug W', Inspector.STATUS_AVAILABLE, None),
            ('Kevin S', Inspector.STATUS_GONE, None),
            ('Greg F', Inspector.STATUS_GONE, None),
            ('John H', Inspector.STATUS_INSPECTION_MANAGER, None),
        ]
        for n1, s, when_str in n:
            when = None if when_str is None else datetime.datetime.fromisoformat(when_str)
            inspector = Inspector(
                name=n1,
                status=s,
                when=when,
            )
            session.add(inspector)
        session.commit()


if __name__ == '__main__':
    main(sys.argv[1:])
