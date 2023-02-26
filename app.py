
from flask import Flask, request
from flask_socketio import SocketIO, emit, join_room, leave_room

app = Flask(__name__)
app.secret_key = 'random secret key!'
socketio = SocketIO(app, cors_allowed_origins="*")

room_user_counts = {}

@socketio.on('join')
def join(message):
    username = message['username']
    room = message['room']
    max_users = 4 
    if room not in room_user_counts:
        room_user_counts[room] = 1
    elif room_user_counts[room] < max_users:
        join_room(room)
        room_user_counts[room] += 1
        print('RoomEvent: {} has joined the room {}\n'.format(username, room))
        emit('ready', username, to=room, skip_sid=request.sid)
    else:
        print('RoomEvent: {} can not join the room {}\n'.format(username, room))
        emit('room_full', {'message': 'Room is full!'}, room=request.sid)


@socketio.on('data')
def transfer_data(message):
    username = message['username']
    room = message['room']
    data = message['data']
    print('DataEvent: {} has sent the data:\n {}\n'.format(username, data))
    emit('data', (data, username), to=room, skip_sid=request.sid)

@socketio.on('leave')
def leave(message):
    username = message['username']
    room = message['room']
    if room in room_user_counts and room_user_counts[room] > 0:
        leave_room(room)
        room_user_counts[room] -= 1
        print('RoomEvent: {} has left the room {}\n'.format(username, room))
        emit('leave', username, to=room, skip_sid=request.sid)

@socketio.on_error_default
def default_error_handler(e):
    print("Error: {}".format(e))
    socketio.stop()


if __name__ == '__main__':
    socketio.run(app, host="0.0.0.0", port=5000)