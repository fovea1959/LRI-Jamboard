import datetime
import json
import logging
import sys

from threading import Lock

import flask
from flask import Flask, render_template, request, session, copy_current_request_context, redirect, url_for
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.exc import NoResultFound
from flask_socketio import SocketIO, emit, disconnect

import LRIDao as Dao
import LRIEntities as E


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
        db_session.close()


@app.errorhandler(NoResultFound)
def no_result_found_handler(error):
    return render_template('404.html'), 404


@app.route('/settings')
def settings():
    db_session = get_db_session()
    teams = []
    for team in db_session.query(E.Team).all():  # type: E.Team
        teams.append(team.as_dict())
    return render_template("settings.html", teams=teams)


@app.route('/locations', methods=['POST'])
def set_locations():
    logging.info("set_locations got: %s", request.form)
    flask.flash(str(request.form))

    location_name = request.form.get('location_text', None)
    if location_name is not None:
        db_session = get_db_session()

        team_numbers = request.form.getlist('team', int)

        if len(team_numbers) > 0:
            for team_number_str in team_numbers:
                team_number = int(team_number_str)
                logging.info("looking up team %d", team_number)
                team = Dao.team_by_number(db_session, team_number)
                logging.info("got team %s", team)
                team.pit_location = location_name
                db_session.add(team)
            db_session.commit()

    return redirect(url_for('settings'))


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
        do_send_time(emitter=socketio.emit)
        socketio.sleep(60)


@socketio.event
def send_teams(message):
    logging.info("got send_teams")
    db_session = get_db_session()
    team_to_inspector_dict = Dao.inspectors_with_team_dict(db_session)
    for team in db_session.query(E.Team).all():  # type: E.Team
        # logging.info("got %s %s", type(team), team)
        d = team.as_dict(team_to_inspector_dict)
        emit('team', d)


def perform_team_pulldown_action(message=None, change_dict=None, db_session=None):
    logging.info('performing team pulldown: %s %s', message, change_dict)
    if change_dict is None:
        return

    team = Dao.team_by_number(db_session, message.get('number', None))
    logging.info('t_pulldown: t before = %s', team.as_dict())
    for n, v in change_dict.items():
        setattr(team, n, v)
    logging.info('t_pulldown: t after  = %s', team.as_dict())
    db_session.add(team)
    db_session.commit()

    inspector_map = Dao.inspectors_with_team_dict(db_session)
    d = team.as_dict(inspector_map)
    logging.info('t_pulldown: sending  = %s', d)

    socketio.emit('team', d)
    do_send_status(db_session=db_session, emitter=socketio.emit)
    do_send_time(emitter=socketio.emit)


@socketio.on('team-pulldown-see')
def team_pulldown_seen(message):
    perform_team_pulldown_action(message, {'seen': True}, db_session=get_db_session())


@socketio.on('team-pulldown-unsee')
def team_pulldown_unseen(message):
    perform_team_pulldown_action(message, {'seen': False}, db_session=get_db_session())


@socketio.on('team-pulldown-weigh')
def team_pulldown_weigh(message):
    perform_team_pulldown_action(message, {'weighed': True}, db_session=get_db_session())


@socketio.on('team-pulldown-unweigh')
def team_pulldown_unweigh(message):
    perform_team_pulldown_action(message, {'weighed': False}, db_session=get_db_session())


@socketio.on('team-pulldown-partial')
def team_pulldown_partial(message):
    perform_team_pulldown_action(message, {'partially_inspected': True}, db_session=get_db_session())


@socketio.on('team-pulldown-unpartial')
def team_pulldown_unpartial(message):
    perform_team_pulldown_action(message, {'partially_inspected': False}, db_session=get_db_session())


@socketio.on('team-pulldown-pass')
def team_pulldown_pass(message):
    perform_team_pulldown_action(message, {'passed_inspection': True}, db_session=get_db_session())


@socketio.on('team-pulldown-unpass')
def team_pulldown_unpass(message):
    perform_team_pulldown_action(message, {'passed_inspection': False}, db_session=get_db_session())


@socketio.event
def send_inspectors(message):
    # logging.info("got send_inspectors")
    do_send_inspectors(db_session=get_db_session())


def get_all_inspectors(db_session=None):
    rv = []
    for item in db_session.query(E.Inspector).all():
        rv.append(item.as_dict())
    return rv


def do_send_inspectors(db_session=None, emitter=emit):
    rv = get_all_inspectors(db_session)
    emitter('inspectors', rv)


@app.route('/debug/i')
def debug_inspectors():
    db_session = get_db_session()
    rv = get_all_inspectors(db_session)
    return rv


def perform_inspector_pulldown_action(message=None, change_dict=None, db_session=None):
    logging.info('doing inspector pulldown: %s %s', message, change_dict)
    if change_dict is None:
        return

    teams_to_update = set()

    inspector = Dao.inspector_by_id(db_session, message.get('id', None))

    if inspector.with_team is not None:
        teams_to_update.add(inspector.with_team)

    logging.info('i_pulldown: i before = %s', inspector.as_dict())
    for n, v in change_dict.items():
        setattr(inspector, n, v)
    logging.info('i_pulldown: i after  = %s', inspector.as_dict())

    if inspector.with_team is not None:
        teams_to_update.add(inspector.with_team)

    db_session.add(inspector)
    logging.debug('Committing %s (inspector)', db_session.connection().connection.dbapi_connection)
    db_session.commit()
    logging.debug('Committed  %s (inspector)', db_session.connection().connection.dbapi_connection)

    if len(teams_to_update) > 0:
        team_with_inspector_dict = Dao.inspectors_with_team_dict(db_session)
        for team_number in teams_to_update:  # type: int
            team = Dao.team_by_number(db_session, team_number)
            d = team.as_dict(team_with_inspector_dict)
            logging.info('i_pulldown: sending %s', d)
            socketio.emit('team', d)

    do_send_inspectors(db_session=db_session, emitter=socketio.emit)
    do_send_time(emitter=socketio.emit)


@socketio.on('inspector-pulldown-available')
def inspector_pulldown_available(message):
    perform_inspector_pulldown_action(message, {
        'status': E.Inspector.STATUS_AVAILABLE,
        'with_team': None,
        'when': None
    }, db_session=get_db_session())


@socketio.on('inspector-pulldown-break')
def inspector_pulldown_break(message):
    perform_inspector_pulldown_action(message, {
        'status': E.Inspector.STATUS_ON_BREAK,
        'with_team': None,
        'when': datetime.datetime.now()
    }, db_session=get_db_session())


@socketio.on('inspector-pulldown-field')
def inspector_pulldown_field(message):
    perform_inspector_pulldown_action(message, {
        'status': E.Inspector.STATUS_ON_FIELD,
        'with_team': None,
        'when': datetime.datetime.now()
    }, db_session=get_db_session())


@socketio.on('inspector-pulldown-gone')
def inspector_pulldown_gone(message):
    perform_inspector_pulldown_action(message, {
        'status': E.Inspector.STATUS_GONE,
        'with_team': None,
        'when': None
    }, db_session=get_db_session())


@socketio.on('inspector-pulldown-im')
def inspector_pulldown_im(message):
    perform_inspector_pulldown_action(message, {
        'status': E.Inspector.STATUS_INSPECTION_MANAGER,
        'with_team': None,
        'when': None
    }, db_session=get_db_session())


@socketio.on('inspector-pulldown-team')
def inspector_pulldown_team(message):
    db_session = get_db_session()
    perform_inspector_pulldown_action(message, {
        'status': E.Inspector.STATUS_WITH_TEAM,
        'with_team': message['team'],
        'when': datetime.datetime.now()
    }, db_session=db_session)

    team = Dao.team_by_number(db_session, message.get('team', None))
    logging.info('before: %s', team.as_dict())
    team.seen = True
    logging.info('after:  %s', team.as_dict())
    db_session.add(team)
    logging.debug('Committing %s (team)', db_session.connection().connection.dbapi_connection)
    db_session.commit()
    logging.debug('Committed  %s (team)', db_session.connection().connection.dbapi_connection)

    team_to_inspector_dict = Dao.inspectors_with_team_dict(db_session)
    socketio.emit('team', team.as_dict(team_to_inspector_dict))
    do_send_time(emitter=socketio.emit)


@socketio.on('add-inspector')
def add_inspector(message):
    # logging.info('got', message)
    db_session = get_db_session()
    name = message.get('name').strip()
    if name != '':
        inspector = E.Inspector(
            name=name,
            status=E.Inspector.STATUS_AVAILABLE,
            when=None,
        )
        db_session.add(inspector)
        db_session.commit()
        socketio.emit('refresh')


@socketio.event
def send_status(message):
    do_send_status(db_session=get_db_session())


def do_send_status(db_session=None, emitter=emit):
    complete = 0
    total = 0
    for item in db_session.query(E.Team).all():  # type: E.Team
        total += 1
        if item.status == item.STATUS_PASSED:
            complete += 1
    rv = G(total=total, complete=complete)
    emitter('status', rv)
    do_send_time(emitter=socketio.emit)


def do_send_time(emitter=emit):
    rv = G(time=datetime.datetime.now().strftime('%l:%M %p'))
    emitter('time', rv)


@socketio.on('*')
def catch_all(event, data):
    logging.info("catch_all: %s %s", event, data)


@socketio.event
def disconnect_request():
    @copy_current_request_context
    def can_disconnect():
        disconnect()

    session['receive_count'] = session.get('receive_count', 0) + 1
    # for this emit we use a callback function
    # when the callback function is invoked we know that the message has been
    # received so it is safe to disconnect
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
    logging.getLogger("sqlalchemy.pool").setLevel(logging.DEBUG)
    logging.getLogger('socketio.server').setLevel(logging.WARNING)
    logging.getLogger('engineio.server').setLevel(logging.WARNING)
    main()
