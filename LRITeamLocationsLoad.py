import argparse
import csv
import logging
import sys

from sqlalchemy.orm import Session

import LRIDao as Dao
from LRIEntities import *


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument('--event', required=True)
    args = parser.parse_args(argv)

    db_filename = f'{args.event}.db'
    team_locations_filename = f'{args.event}_team_locations.csv'

    with (Session(Dao.engine(db_filename)) as session):
        with open(team_locations_filename, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                team = Dao.team_by_number(session, int(row['number']))
                team.pit_location = row['pit_location']
                session.add(team)
            session.commit()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    main(sys.argv[1:])
