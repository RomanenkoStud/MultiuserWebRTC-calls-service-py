
from flask import Flask, request, render_template
from flask_socketio import SocketIO, emit, join_room, leave_room
import spacy
from nltk.corpus import wordnet
from transformers import pipeline
import wikipediaapi
import requests
import json
from collections import deque

app = Flask(__name__)
app.secret_key = 'random secret key!'
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins="*")

# Store number of users for each  room
room_user_counts = {}
# Store previous transcripts for each room
room_transcripts = {}
# Set the maximum number of transcripts to store per room
TRANSCRIPTS_DEPTH = 10

# Load the pre-trained pipeline for text classification
classifier = pipeline("text-classification", model="jonaskoenig/topic_classification_04")

# Load nlp model
nlp = spacy.load('en_core_web_sm')

@app.route("/")
def home():
    return render_template('index.html')

@socketio.on('join')
def join(message):
    username = message['username']
    room = message['room']
    max_users = 4 
    if room not in room_transcripts:
        room_transcripts[room] = []
    if room not in room_user_counts:
        join_room(room)
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
        if(room_user_counts[room] == 0):
            room_transcripts[room] = []

@socketio.on('message')
def send_message(message):
    username = message['username']
    room = message['room']
    message = message['message']
    print('RoomEvent: {} has sent message to room {}\n'.format(username, room))
    emit('message', (message, username), to=room, skip_sid=request.sid)
    
@socketio.on('user_speech')
def send_speech(message):
    username = message['username']
    room = message['room']
    transcript = message['transcript']
    print('RoomEvent: {} has said {} to room {}\n'.format(username, transcript, room))
    if transcript.strip() != '':
            # Get the deque for this room or create a new one
            room_deque = room_transcripts.get(room, deque(maxlen=TRANSCRIPTS_DEPTH))
            # Append the current transcript to the deque
            room_deque.append({'username': username, 'transcript': transcript})
            # Store the updated deque for this room
            room_transcripts[room] = room_deque
            
            theme = guess_theme(room_transcripts[room])
            room_transcripts[room][-1]['topic'] = theme
            print('RoomEvent: {} theme suggestion to room {}\n'.format(theme, room))
            keyword = guess_keyword(transcript)
            print('RoomEvent: {} keyword suggestion to room {}\n'.format(keyword, room))
            if(keyword != None):
                hint = get_fact(keyword)
                print('RoomEvent: {} fact to room {}\n'.format(hint, room))
                emit('fact', hint, to=room)
                hint = get_news(keyword)
                print('RoomEvent: {} news to room {}\n'.format(hint, room))
                emit('news', hint, to=room)
    
def guess_theme(transcripts):
    """
    This function takes a transcripts list as input and returns predicted topic.
    """
    # Combine all transcripts into a single text
    text = ' '.join([t['transcript'] for t in transcripts])
    
    # Run the transcripts through the pipeline to get the predicted labels
    result = classifier(text)[0]

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
    for chunk in doc.noun_chunks:
        if chunk.root.pos_ in ['NOUN', 'PROPN']:
            keyword = chunk.text.lower()
            # Look for adjectives and verbs that modify the noun chunk
            for child in chunk.root.children:
                if child.pos_ in ['ADJ', 'VERB']:
                    keyword = '{} {}'.format(child.text.lower(), keyword)
            # Check if the keyword is a term or a named entity
            if any(wordnet.synsets(keyword)):
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
    wikipedia = wikipediaapi.Wikipedia('en')
    page = wikipedia.page(topic)
    summary = page.summary
    fact = summary.split('.')[0] + '.'
    return fact

def get_news(topic):
    """
    This function takes a topic as input and returns a list of news articles 
    related to that topic from the NYT.
    """
    # API key for the New York Times API
    api_key = "G16k4MYvuV34brKi17Z7Dh9xar9Ycef2"
    # URL for the New York Times API endpoint
    url = "https://api.nytimes.com/svc/search/v2/articlesearch.json"
    # Parameters for the API request
    params = {
        "q": topic,
        "api-key": api_key
    }
    # Make a GET request to the New York Times API with the given topic as a parameter
    response = requests.get(url, params=params)
    # Parse the response and extract the news articles
    news_json = json.loads(response.text)
    articles = news_json["response"]["docs"]
    # Extract the headline and URL of each article and store them in a list
    news_list = []
    for article in articles:
        headline = article["headline"]["main"]
        url = article["web_url"]
        news_list.append((headline))
    return news_list[:3]

@socketio.on_error_default
def default_error_handler(e):
    print("Error: {}".format(e))
    socketio.stop()


if __name__ == '__main__':
    socketio.run(app, host="0.0.0.0", port=8000)