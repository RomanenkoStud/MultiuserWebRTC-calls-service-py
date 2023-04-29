
from flask import Flask, request, render_template
from flask_socketio import SocketIO, emit, join_room, leave_room, rooms
import requests

app = Flask(__name__)
app.secret_key = 'random secret key!'
socketio = SocketIO(app, ping_interval=10, ping_timeout=5, async_mode='eventlet', cors_allowed_origins="*")

API_HOST_ADDRESS = 'https://server-app-spring.azurewebsites.net/api/v1/rooms'

@app.route("/")
def home():
    return render_template('index.html')

@socketio.on('join')
def join(message):
    username = message['username']
    room_id = message['room']
    print('Join request from {} to room {}\n'.format(username, room_id))

    # Retrieve room info from the API
    response = requests.get(f"{API_HOST_ADDRESS}/connect?id={room_id}")
    if response.status_code == requests.codes.ok:
        room = response.json()
        print('Room data: {}\n'.format(room))
        if not room['private']:
            # Join the room with null password
            response = requests.post(f"{API_HOST_ADDRESS}/connect/{room_id}",
                                json={"sid": request.sid, "username": username, "password": None})
            if response.status_code == requests.codes.ok:
                join_room(room_id, sid=request.sid)
                emit('joined', room=request.sid)
            else:
                emit('join_error', response.text, room=request.sid)
        else:
            # Ask the user for a password
            emit('password', room=request.sid)
    else:
        emit('join_error', response.text, room=request.sid)

@socketio.on('join_with_password')
def join_with_password(message):
    username = message['username']
    room_id = message['room']
    password = message['password']
    print('Join request from {} to private room {}\n'.format(username, room_id))

    # Join the room with the provided password
    response = requests.post(f"{API_HOST_ADDRESS}/connect/{room_id}",
                            json={"sid": request.sid, "username": username, "password": password})
    if response.status_code == requests.codes.ok:
        join_room(room_id, sid=request.sid)
        emit('joined', room=request.sid)
    else:
        emit('join_error', response.text, room=request.sid)

@socketio.on('start_connection')
def ready(message):
    user = message['user']
    room = message['room']
    emit('ready', (user, request.sid), to=room, skip_sid=request.sid)

@socketio.on('end_connection')
def end(message):
    room = message['room']
    print('RoomEvent: {} has end stream the room {}\n'.format(request.sid, room))
    emit('end', request.sid, to=room, skip_sid=request.sid)

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
    leave_room(room, sid=request.sid)
    print('RoomEvent: {} has left the room {}\n'.format(request.sid, room))
    response = requests.delete(f"{API_HOST_ADDRESS}/connect/{room}",
                                params={"sid": request.sid})
    if response.status_code != requests.codes.no_content:
        print(f"Error disconnecting user from room {room}: {response.status_code}")

@socketio.on('message')
def send_message(message):
    username = message['username']
    room = message['room']
    message = message['message']
    print('RoomEvent: {} has sent message to room {}\n'.format(username, room))
    emit('message', (message, username), to=room, skip_sid=request.sid)

@socketio.on('disconnect')
def disconnect():
    for room in rooms(request.sid):
        leave_room(room, sid=request.sid)
        print('RoomEvent: {} has left the room {}\n'.format(request.sid, room))
        emit('end', request.sid, to=room)
        response = requests.delete(f"{API_HOST_ADDRESS}/connect/{room}",
                                params={"sid": request.sid})
        if response.status_code != requests.codes.no_content:
            print(f"Error disconnecting user from room {room}: {response.status_code}")

@socketio.on_error_default
def default_error_handler(e):
    print("Error: {}".format(e))
    socketio.stop()


if __name__ == '__main__':
    socketio.run(app, host="0.0.0.0", port=8000)