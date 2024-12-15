import datetime
import json
import logging
import sys

from threading import Lock

import flask
from flask import Flask, render_template, url_for, redirect, request, flash, session, copy_current_request_context
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.exc import NoResultFound
from flask_socketio import SocketIO, emit, disconnect

import LRIDao as Dao
import LRIEntities as E
from LRIEntities import Team


class MyEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, datetime.datetime):
            return o.isoformat()
        if isinstance(o, datetime.timedelta):
            return o.total_seconds()
        return o.__dict__


class MyAwesomeJsonWrapper(object):
    """https://github.com/miguelgrinberg/flask-socketio/issues/274#issuecomment-231206374"""
    @staticmethod
    def dumps(*args, **kwargs):
        if 'cls' not in kwargs:
            kwargs['cls'] = MyEncoder
        return json.dumps(*args, **kwargs)

    @staticmethod
    def loads(*args, **kwargs):
        return json.loads(*args, **kwargs)


Session = sessionmaker(bind=Dao.engine)
app = Flask(__name__)

# Set this variable to "threading", "eventlet" or "gevent" to test the
# different async modes, or leave it set to None for the application to choose
# the best option based on installed packages.
async_mode = None

socketio = SocketIO(app, async_mode=async_mode, logger=True, engineio_logger=True, json=MyAwesomeJsonWrapper)
thread = None
thread_lock = Lock()


class G:
    def __init__(self, *initial_data, **kwargs):
        for dictionary in initial_data:
            for key in dictionary:
                setattr(self, key, dictionary[key])
        for key in kwargs:
            setattr(self, key, kwargs[key])


def get_db_session():
    # https://flask.palletsprojects.com/en/stable/appcontext/#storing-data
    if 'db_session' not in flask.g:
        flask.g.db_session = Session()
        logging.info("session %s created", flask.g.db_session)
    return flask.g.db_session


@app.teardown_appcontext
def shutdown_session(response_or_exc):
    db_session = flask.g.pop('db_session', None)

    if db_session is not None:
        if db_session.new or db_session.deleted or db_session.dirty:
            logging.info("session %s is being committed", db_session)
            db_session.commit()
        else:
            logging.info("session %s is clean, no commit", db_session)


@app.errorhandler(NoResultFound)
def no_result_found_handler(error):
    return render_template('404.html'), 404


@app.route('/')
def index():
    teams = []
    team_data = []
    for item in get_db_session().query(E.Team).all():
        g = G(team=item)
        teams.append(g)
        team_data.append(g)
    n_rows, n_cols = (5, 8)
    if len(teams) < 36:
        n_rows, n_cols = (5, 7)
    elif len(teams) >= 42:
        n_rows, n_cols = (6, 8)
    elif len(teams) > 40:
        n_rows, n_cols = (6, 7)
    # make last row complete
    for i in range(len(teams), n_rows * n_cols):
        teams.append(G(team=None))

    """https://stackoverflow.com/a/14681687"""
    row_data = [teams[i:i + n_cols] for i in range(0, len(teams), n_cols)]

    inspectors = [i for i in get_db_session().query(E.Inspector).all()]

    return render_template("index.html", team_data=team_data, row_data=row_data, inspectors=inspectors)


@socketio.on('*')
def catch_all(event, data):
    logging.info("catch_all got %s: %s", event, data)


def background_thread():
    app.app_context()
    """Example of how to send server generated events to clients."""
    db_session = Session()
    while True:
        logging.info("updating inspectors")
        do_send_inspectors(db_session=db_session, emitter=socketio.emit)
        socketio.sleep(60)


@socketio.event
def send_teams(message):
    logging.info("got send_teams")
    for item in get_db_session().query(E.Team).all():
        d = item.as_dict()
        emit('team', d)


def do_team_pulldown(message=None, change_dict=None, db_session=None):
    logging.info('doing team pulldown: %s %s', message, change_dict)
    if change_dict is None:
        return

    team = Dao.team_by_number(db_session, message.get('number', None))
    logging.info('before: %s', team.as_dict())
    for n, v in change_dict.items():
        setattr(team, n, v)
    logging.info('after:  %s', team.as_dict())
    db_session.add(team)
    db_session.commit()

    socketio.emit('team', team.as_dict())
    do_send_status(db_session=db_session, emitter=socketio.emit)


@socketio.on('team-pulldown-see')
def team_pulldown_seen(message):
    do_team_pulldown(message, {'seen': True}, db_session=get_db_session())


@socketio.on('team-pulldown-unsee')
def team_pulldown_unseen(message):
    do_team_pulldown(message, {'seen': False}, db_session=get_db_session())


@socketio.on('team-pulldown-weigh')
def team_pulldown_weigh(message):
    do_team_pulldown(message, {'weighed': True}, db_session=get_db_session())


@socketio.on('team-pulldown-unweigh')
def team_pulldown_unweigh(message):
    do_team_pulldown(message, {'weighed': False}, db_session=get_db_session())


@socketio.on('team-pulldown-pass')
def team_pulldown_pass(message):
    do_team_pulldown(message, {'passed_inspection': True}, db_session=get_db_session())


@socketio.on('team-pulldown-unpass')
def team_pulldown_unpass(message):
    do_team_pulldown(message, {'passed_inspection': False}, db_session=get_db_session())


@socketio.event
def send_inspectors(message):
    logging.info("got send_inspectors")
    do_send_inspectors(db_session=get_db_session())


def do_send_inspectors(db_session=None, emitter=emit):
    for item in db_session.query(E.Inspector).all():
        d = item.as_dict()
        emitter('inspector', d)


def do_inspector_pulldown(message=None, change_dict=None, db_session=None):
    logging.info('doing inspector pulldown: %s %s', message, change_dict)
    if change_dict is None:
        return

    inspector = Dao.inspector_by_id(db_session, message.get('id', None))
    logging.info('before: %s', inspector.as_dict())
    for n, v in change_dict.items():
        setattr(inspector, n, v)
    logging.info('after:  %s', inspector.as_dict())
    db_session.add(inspector)
    db_session.commit()

    socketio.emit('inspector', inspector.as_dict())


@socketio.on('inspector-pulldown-available')
def inspector_pulldown_available(message):
    do_inspector_pulldown(message,{
        'status': E.Inspector.STATUS_AVAILABLE,
        'with_team': None,
        'when': None
    }, db_session=get_db_session())


@socketio.on('inspector-pulldown-break')
def inspector_pulldown_break(message):
    do_inspector_pulldown(message,{
        'status': E.Inspector.STATUS_ON_BREAK,
        'with_team': None,
        'when': datetime.datetime.now()
    }, db_session=get_db_session())


@socketio.on('inspector-pulldown-field')
def inspector_pulldown_field(message):
    do_inspector_pulldown(message,{
        'status': E.Inspector.STATUS_ON_FIELD,
        'with_team': None,
        'when': datetime.datetime.now()
    }, db_session=get_db_session())


@socketio.on('inspector-pulldown-gone')
def inspector_pulldown_gone(message):
    do_inspector_pulldown(message,{
        'status': E.Inspector.STATUS_GONE,
        'with_team': None,
        'when': None
    }, db_session=get_db_session())


@socketio.on('inspector-pulldown-team')
def inspector_pulldown_gone(message):
    db_session = get_db_session()
    do_inspector_pulldown(message,{
        'status': E.Inspector.STATUS_WITH_TEAM,
        'with_team': message['team'],
        'when': datetime.datetime.now()
    }, db_session=db_session)

    team = Dao.team_by_number(db_session, message.get('team', None))
    logging.info('before: %s', team.as_dict())
    team.seen = True
    logging.info('after:  %s', team.as_dict())
    db_session.add(team)
    db_session.commit()

    logging.info('aafter: %s', team.as_dict())
    socketio.emit('team', team.as_dict())


@socketio.event
def send_status(message):
    do_send_status(db_session=get_db_session())


def do_send_status(db_session=None, emitter=emit):
    complete = 0
    total = 0
    for item in db_session.query(E.Team).all():
        total += 1
        if item.status == item.STATUS_PASSED:
            complete += 1
    rv = G(total=total, complete=complete)
    emitter('status', rv)


@socketio.on('*')
def catch_all(event, data):
    logging.info ("catch_all: %s %s", event, data)


@socketio.event
def disconnect_request():
    @copy_current_request_context
    def can_disconnect():
        disconnect()

    session['receive_count'] = session.get('receive_count', 0) + 1
    # for this emit we use a callback function
    # when the callback function is invoked we know that the message has been
    # received and it is safe to disconnect
    emit('disconnect_response',
         {'data': 'Disconnected!'},
         callback=can_disconnect)


@socketio.event
def connect():
    global thread
    with thread_lock:
        if thread is None:
            thread = socketio.start_background_task(background_thread)


@socketio.on('disconnect')
def disconnect():
    print('Client disconnected', request.sid)


def main():
    app.secret_key = 'super secret key'
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
    app.debug = True
    socketio.run(app, allow_unsafe_werkzeug=True)


class CustomLogFormatter(logging.Formatter):
    # derived from https://stackoverflow.com/a/71336115
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name_cache = {}

    def format(self, record):
        saved_name = record.name  # save and restore for other formatters if desired
        abbrev = self.name_cache.get(saved_name, None)
        if abbrev is None:
            parts = saved_name.split('.')
            if len(parts) > 1:
                abbrev = '.'.join(p[0] for p in parts[:-1])
                abbrev = '.'.join((abbrev, parts[-1]))
            else:
                abbrev = saved_name
            self.name_cache[saved_name] = abbrev
        record.name = abbrev
        result = super().format(record)
        return result


if __name__ == '__main__':
    h = logging.StreamHandler(stream=sys.stderr)
    f = CustomLogFormatter("%(asctime)s %(levelname)-8s %(name)-20s %(message)s")
    h.setFormatter(f)
    root = logging.getLogger()
    root.addHandler(h)
    root.setLevel(logging.INFO)
    # need to look at https://stackoverflow.com/a/73094988 to handle access logs

    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.pool").setLevel(logging.INFO)
    logging.getLogger('socketio.server').setLevel(logging.WARNING)
    logging.getLogger('engineio.server').setLevel(logging.WARNING)
    main()
