from LRIEntities import *

from sqlalchemy.orm import Session
from sqlalchemy import select, create_engine
from sqlalchemy.engine.result import ScalarResult

engine = create_engine('sqlite:///LRI.db', echo=False)
