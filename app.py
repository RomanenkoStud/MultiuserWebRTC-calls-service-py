
from flask import Flask, request, render_template
from flask_socketio import SocketIO, emit, join_room, leave_room

app = Flask(__name__)
app.secret_key = 'random secret key!'
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins="*")

# Store number of users for each  room
room_user_counts = {}

@app.route("/")
def home():
    return render_template('index.html')

@socketio.on('join')
def join(message):
    user = message['user']
    room = message['room']
    max_users = 4 
    if room not in room_user_counts:
        join_room(room)
        room_user_counts[room] = 1
    elif room_user_counts[room] < max_users:
        join_room(room)
        room_user_counts[room] += 1
        print('RoomEvent: {} has joined the room {}\n'.format(user, room))
        emit('ready', (user, request.sid), to=room, skip_sid=request.sid)
    else:
        print('RoomEvent: {} can not join the room {}\n'.format(user, room))
        emit('room_full', {'message': 'Room is full!'}, room=request.sid)

@socketio.on('data')
def transfer_data(message):
    sid = message['sid']
    data = message['data']
    print('DataEvent: {} has sent the data:\n {}\n'.format(request.sid, data))
    emit('data', (data, request.sid), to=sid)
    
@socketio.on('user_info')
def user_info(message):
    sid = message['sid']
    info = message['info']
    print('DataEvent: {} has sent the info:\n {}\n'.format(request.sid, info))
    emit('user_info', (info, request.sid), to=sid)

@socketio.on('leave')
def leave(message):
    room = message['room']
    if room in room_user_counts and room_user_counts[room] > 0:
        leave_room(room)
        room_user_counts[room] -= 1
        print('RoomEvent: {} has left the room {}\n'.format(request.sid, room))
        emit('leave', request.sid, to=room, skip_sid=request.sid)

@socketio.on('message')
def send_message(message):
    username = message['username']
    room = message['room']
    message = message['message']
    print('RoomEvent: {} has sent message to room {}\n'.format(username, room))
    emit('message', (message, username), to=room, skip_sid=request.sid)

@socketio.on_error_default
def default_error_handler(e):
    print("Error: {}".format(e))
    socketio.stop()


if __name__ == '__main__':
    socketio.run(app, host="0.0.0.0", port=8000)