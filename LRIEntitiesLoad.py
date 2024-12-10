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
            team = E.Team(
                team_number=team_dict['team_number'],
                team_name=team_dict['nickname'],
                school_name=team_dict['school_name'],
                city=team_dict['city']
            )
            session.add(team)

        session.commit()


if __name__ == '__main__':
    main(sys.argv[1:])
