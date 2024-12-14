import datetime
import json
import os
import sys

from sqlalchemy.orm import Session

import LRIEntities as E
import LRIDao as Dao


def main(argv):
    try:
        os.remove('LRI.db')
    except FileNotFoundError:
        pass
    E.Base.metadata.create_all(Dao.engine)

    with open('2022misjo_teams.json', 'r') as f:
        blue_alliance = json.load(f)
    print('# of teams:', len(blue_alliance))

    with (Session(Dao.engine) as session):
        for team_dict in blue_alliance:  # type: dict
            team_number = team_dict['team_number']
            team = E.Team(
                number=team_number,
                name=team_dict['nickname'],
                school_name=team_dict['school_name'],
                city=team_dict['city'],
                weighed=team_number in (1940, 3620),
                inspected=team_number in (3620, ),
            )
            session.add(team)
        session.commit()

        n = [
            ('Tearesa W', 'available', None),
            ('Doug W', 'on break', '20241213 11:00'),
            ('Kevin S', 'available', None),
            ('Greg F', 'available', None),
        ]
        for n1, s, when_str in n:
            when = None if when_str is None else datetime.datetime.fromisoformat(when_str)
            inspector = E.Inspector(
                name=n1,
                status=s,
                when=when,
            )
            session.add(inspector)
        session.commit()


if __name__ == '__main__':
    main(sys.argv[1:])
