import json
import logging
import sys

from threading import Lock

import flask
from flask import Flask, render_template, url_for, redirect, request, flash, session, copy_current_request_context
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.exc import NoResultFound
from flask_socketio import SocketIO, emit, join_room, leave_room, \
    close_room, rooms, disconnect

import LRIDao as Dao
import LRIEntities as E

Session = sessionmaker(bind=Dao.engine)
app = Flask(__name__)

# Set this variable to "threading", "eventlet" or "gevent" to test the
# different async modes, or leave it set to None for the application to choose
# the best option based on installed packages.
async_mode = None

socketio = SocketIO(app, async_mode=async_mode, logger=True, engineio_logger=True)
thread = None
thread_lock = Lock()


class MyEncoder(json.JSONEncoder):
    def default(self, o):
        return o.__dict__


class G:
    def __init__(self, *initial_data, **kwargs):
        for dictionary in initial_data:
            for key in dictionary:
                setattr(self, key, dictionary[key])
        for key in kwargs:
            setattr(self, key, kwargs[key])


def get_db_session():
    # https://flask.palletsprojects.com/en/stable/appcontext/#storing-data
    if 'db' not in flask.g:
        flask.g.db_session = Session()
        logging.info("Made session %s", flask.g.db_session)
    return flask.g.db_session


@app.teardown_appcontext
def shutdown_session(response_or_exc):
    db_session = flask.g.pop('db_session', None)

    if db_session is not None:
        if db_session.new or db_session.deleted or db_session.dirty:
            logging.info("Session %s is being committed", db_session)
            db_session.commit()
        else:
            logging.info("Session %s is clean, no commit", db_session)


@app.errorhandler(NoResultFound)
def no_result_found_handler(error):
    return render_template('404.html'), 404


@app.route('/')
def index():
    data = []
    for item in get_db_session().query(E.Team).all():
        g = G(team=item)
        data.append(g)
    n_rows, n_cols = (5, 8)
    if len(data) < 36:
        n_rows, n_cols = (5, 7)
    elif len(data) >= 42:
        n_rows, n_cols = (6, 8)
    elif len(data) > 40:
        n_rows, n_cols = (6, 7)
    for i in range(len(data), n_rows * n_cols):
        data.append(G(team=None))

    """https://stackoverflow.com/a/14681687"""
    data = [data[i:i + n_cols] for i in range(0, len(data), n_cols)]

    return render_template("index.html", team_rows = data)


@socketio.on('*')
def catch_all(event, data):
    session['receive_count'] = session.get('receive_count', 0) + 1
    emit('test_response',
         {'data': [event, data], 'count': session['receive_count']})


def background_thread():
    """Example of how to send server generated events to clients."""
    count = 0
    while True:
        socketio.sleep(10)
        count += 1
        socketio.emit('test_response',
                      {'data': 'Server generated event', 'count': count})


@app.route('/test')
def test():
    return render_template('test.html', async_mode=socketio.async_mode)


@socketio.event
def send_teams(message):
    logging.info("got send_teams")
    for item in get_db_session().query(E.Team).all():
        emit('team', item.as_dict())



@socketio.event
def test_event(message):
    session['receive_count'] = session.get('receive_count', 0) + 1
    emit('test_response',
         {'data': message['data'], 'count': session['receive_count']})


@socketio.event
def test_broadcast_event(message):
    session['receive_count'] = session.get('receive_count', 0) + 1
    emit('test_response',
         {'data': message['data'], 'count': session['receive_count']},
         broadcast=True)


@socketio.event
def join(message):
    join_room(message['room'])
    session['receive_count'] = session.get('receive_count', 0) + 1
    emit('test_response',
         {'data': 'In rooms: ' + ', '.join(rooms()),
          'count': session['receive_count']})


@socketio.event
def leave(message):
    leave_room(message['room'])
    session['receive_count'] = session.get('receive_count', 0) + 1
    emit('test_response',
         {'data': 'In rooms: ' + ', '.join(rooms()),
          'count': session['receive_count']})


@socketio.on('close_room')
def on_close_room(message):
    session['receive_count'] = session.get('receive_count', 0) + 1
    emit('test_response', {'data': 'Room ' + message['room'] + ' is closing.',
                         'count': session['receive_count']},
         to=message['room'])
    close_room(message['room'])


@socketio.event
def test_room_event(message):
    session['receive_count'] = session.get('receive_count', 0) + 1
    emit('test_response',
         {'data': message['data'], 'count': session['receive_count']},
         to=message['room'])


@socketio.on('*')
def catch_all(event, data):
    session['receive_count'] = session.get('receive_count', 0) + 1
    emit('test_response',
         {'data': [event, data], 'count': session['receive_count']})


@socketio.event
def disconnect_request():
    @copy_current_request_context
    def can_disconnect():
        disconnect()

    session['receive_count'] = session.get('receive_count', 0) + 1
    # for this emit we use a callback function
    # when the callback function is invoked we know that the message has been
    # received and it is safe to disconnect
    emit('test_response',
         {'data': 'Disconnected!', 'count': session['receive_count']},
         callback=can_disconnect)


@socketio.event
def test_ping():
    emit('test_pong')


@socketio.event
def connect():
    global thread
    with thread_lock:
        if thread is None:
            thread = socketio.start_background_task(background_thread)
    emit('test_response', {'data': 'Connected', 'count': 0})


@socketio.on('disconnect')
def test_disconnect():
    print('Client disconnected', request.sid)


def main():
    app.secret_key = 'super secret key'
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
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

    logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.pool").setLevel(logging.INFO)
    main()
