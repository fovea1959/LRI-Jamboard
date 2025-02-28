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
    parser.add_argument('--create', action='store_true')
    parser.add_argument('--teams')
    parser.add_argument('--inspectors')
    args = parser.parse_args(argv)

    if args.create:
        logging.info ("Deleting database file")
        try:
            os.remove('LRI.db')
            logging.info("...deleted")
        except FileNotFoundError:
            pass
        logging.info ("Creating database file")
        Base.metadata.create_all(Dao.engine)
        logging.info("...created")

    with (Session(Dao.engine) as session):
        if args.teams:
            with open(args.teams, 'r') as f:
                blue_alliance = json.load(f)
            logging.info("read %d teams from %s", len(blue_alliance), args.teams)

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
            with open(args.inspectors, 'r') as file:
                for line in file:
                    name = line.strip()
                    if len(name) > 0:
                        names.append(name)
            logging.info("read %d inspectors from %s", len(names), args.inspectors)

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
