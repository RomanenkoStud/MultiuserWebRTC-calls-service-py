
from flask import Flask, request, render_template
from flask_socketio import SocketIO, emit, join_room, leave_room, rooms
import spacy
from nltk.corpus import wordnet
from transformers import pipeline
import wikipediaapi
import requests
import json

app = Flask(__name__)
app.secret_key = 'random secret key!'
socketio = SocketIO(app, ping_interval=10, ping_timeout=5, async_mode='eventlet', cors_allowed_origins="*")

API_HOST_ADDRESS = 'https://server-app-spring.azurewebsites.net/api/v1/rooms'

# Store last transcripts for each room
room_topic = {}

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
                if room_id not in room_topic:
                    room_topic[room_id] = None
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
        if room_id not in room_topic:
            room_topic[room_id] = None
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

# Load the pre-trained pipeline for text classification
# classifier = pipeline("text-classification", model="jonaskoenig/topic_classification_04")
classifier = pipeline('text-classification', model='./bert/fine-tuned-bert', tokenizer='bert-base-multilingual-uncased')

# Load nlp model
#nlp = spacy.load('en_core_web_sm')
nlp = spacy.load("uk_core_news_sm")

@socketio.on('user_speech')
def send_speech(message):
    username = message['username']
    room = message['room']
    transcript = message['transcript']
    print('RoomEvent: {} has said {} to room {}\n'.format(username, transcript, room))
    if transcript.strip() != '':
            theme = guess_theme(transcript)
            print('RoomEvent: {} theme suggestion to room {}\n'.format(theme, room))
            keyword = guess_keyword(transcript)
            print('RoomEvent: {} keyword suggestion to room {}\n'.format(keyword, room))
            isTopicChanged = (room_topic[room] == None or (room_topic[room] != theme))
            room_topic[room] = theme
            if(isTopicChanged and keyword != None):
                hint = get_fact(keyword)
                print('RoomEvent: {} fact to room {}\n'.format(hint, room))
                emit('fact', hint, to=room)
                hint = get_news(keyword)
                print('RoomEvent: {} news to room {}\n'.format(hint, room))
                emit('news', hint, to=room)
    
def guess_theme(transcript):
    """
    This function takes a transcript string as input and returns predicted topic.
    """
    
    # Run the transcript through the pipeline to get the predicted labels
    result = classifier(transcript)[0]

    # Set threashold for the predicted topic accuracy
    threashold = 0.9
    
    if(result['score'] >= threashold):
        return result['label']
    else:
        return None
    
def guess_keyword(transcript):
    """
    This function takes a transcript as input and returns predicted keyword.
    """
    doc = nlp(transcript)
    # Identify the main keywords of the conversation
    keywords = []
    for token in doc:
        if token.pos_ in ['NOUN', 'PROPN']:
            keyword = token.text.lower()
            # Look for adjectives and verbs that modify the noun chunk
            for child in token.children:
                if child.pos_ in ['ADJ', 'VERB']:
                    keyword = '{} {}'.format(child.text.lower(), keyword)
            keywords.append(keyword)
    # Count the frequency of each keyword
    freq = {}
    for keyword in keywords:
        if keyword not in freq:
            freq[keyword] = 1
        else:
            freq[keyword] += 1
    # Sort keywords by frequency and return the most frequent ones
    sorted_keywords = sorted(freq.items(), key=lambda x: x[1], reverse=True)
    if len(sorted_keywords) > 0:
        return sorted_keywords[0][0]
    else:
        return None
    
def get_fact(topic):
    """
    This function takes a topic as input and returns fact from Wikipedia.
    """
    wikipedia = wikipediaapi.Wikipedia('uk')
    page = wikipedia.page(topic)
    summary = page.summary
    fact = summary.split('.')[0] + '.'
    return fact

def get_news(topic):
    """
    This function takes a topic as input and returns a list of news articles 
    related to that topic from Event Registry.
    """
    # API key for Event Registry
    api_key = "a2778dc1-a14e-4b66-ab01-b22db09209e9"
    # URL for Event Registry API endpoint
    url = "http://eventregistry.org/api/v1/article/getArticles"
    # Parameters for the API request
    payload = {
        "action": "getArticles",
        "keyword": topic,
        "articlesCount": 3,
        "articlesSortBy": "date",
        "articlesSortByAsc": False,
        "resultType": "articles",
        "dataType": ["news"],
        "apiKey": api_key,
        "lang": "ukr"
        #"lang": "eng"
    }
    # Make a POST request to Event Registry API with the given topic as a parameter
    response = requests.post(url, json=payload)
    # Parse the response and extract the news articles
    news_json = response.json()
    articles = news_json["articles"]["results"]
    # Extract the headline and URL of each article and store them in a list
    news_list = []
    for article in articles:
        headline = article["title"]
        url = article["url"]
        news_list.append((headline, url))
    return news_list[:3]

@socketio.on_error_default
def default_error_handler(e):
    print("Error: {}".format(e))
    socketio.stop()


if __name__ == '__main__':
    socketio.run(app, host="0.0.0.0", port=8000)