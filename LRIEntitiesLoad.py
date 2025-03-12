import argparse
import json
import logging
import os
import sys

from sqlalchemy.orm import Session

import LRIDao as Dao
from LRIEntities import *


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument('--teams', action='store_true')
    parser.add_argument('--inspectors', action='store_true')
    parser.add_argument('--create', action='store_true')
    parser.add_argument('--event', required=True)
    args = parser.parse_args(argv)

    db_filename = f'{args.event}.db'
    if args.create:
        logging.info ("Deleting database file %s", db_filename)
        try:
            os.remove(db_filename)
            logging.info("...deleted")
        except FileNotFoundError:
            pass
        logging.info ("Creating database file %s", db_filename)
        Base.metadata.create_all(Dao.engine(db_filename))
        logging.info("...created")

    with (Session(Dao.engine(db_filename)) as session):
        if args.teams:
            teams_filename = f'{args.event}_teams.json'
            with open(teams_filename, 'r') as f:
                blue_alliance = json.load(f)
            logging.info("read %d teams from %s", len(blue_alliance), teams_filename)

            if len(blue_alliance) > 0:
                num_rows_deleted = session.query(Team).delete()
                logging.info("deleted %d teams from database", num_rows_deleted)

                for team_dict in blue_alliance:  # type: dict
                    team_number = team_dict['team_number']
                    team = Team(
                        number=team_number,
                        name=team_dict['nickname'],
                        school_name=team_dict['school_name'],
                        city=team_dict['city'],
                    )
                    session.add(team)
                session.commit()

        if args.inspectors:
            names = []
            inspectors_filename = f'{args.event}_inspectors.txt'
            with open(inspectors_filename, 'r') as file:
                for line in file:
                    name = line.strip()
                    if len(name) > 0:
                        names.append(name)
            logging.info("read %d inspectors from %s", len(names), inspectors_filename)

            if len(names) > 0:
                num_rows_deleted = session.query(Inspector).delete()
                logging.info("deleted %d inspectors from database", num_rows_deleted)

                for name in names:
                    is_lri = False
                    if name[0] == '*':
                        name = name[1:]
                        is_lri = True
                    inspector = Inspector(
                        name=name,
                        status=Inspector.STATUS_GONE,
                        lri = is_lri,
                    )
                    session.add(inspector)
                session.commit()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    main(sys.argv[1:])
