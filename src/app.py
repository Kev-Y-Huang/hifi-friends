from flask import (
    Flask, 
    render_template, 
    request,
    Response
)

from client import Client
from ast import literal_eval
import os
import threading

client = Client()

app = Flask(__name__)

def run_client():
    client.run_client()

client_thread = threading.Thread(target=run_client)
client_thread.start()

# Dummy list of songs
songs = []
# Dummy queue of songs
queue = []


@app.route('/')
def index():
    return render_template('index.html', songs=songs, queue=queue)


@app.route('/get_songs', methods=['GET'])
def get_songs():
    '''
    Flask route to update the list of songs, calls the get_updated_songs() function
    '''
    global songs
    try:
        temp_songs = client.get_song_list()
        if temp_songs[:7] == ':songs:':
            songs = literal_eval(temp_songs[7:])
        else:
            pass
    except:
        return {'error': 'Unable to retrieve songs'}, 400
    return songs


@app.route('/upload_song', methods=['POST'])
def upload_song():
    '''
    Flask route to upload a song to the server
    '''
    if 'file' in request.files:
        file = request.files['file']
        # Save the uploaded file to a desired location
        if file.filename in songs:
            return {'error': 'Song already exists.'}, 400
        file.save(f'server_files/{file.filename}')
        songs.append(file.filename)
        # Return a success message or relevant data
        return {'message': 'Song uploaded successfully.'}, 200

    # Return an error message if no file was uploaded
    return {'error': 'No song file uploaded.'}, 400


@app.route('/get_queue', methods=['GET'])
def get_queue():
    '''
    Flask route to update the list of songs, calls the get_updated_songs() function
    '''
    global queue
    try:
        temp_queue = client.get_current_queue()
        if temp_queue[:7] == ':queue:':
            queue = literal_eval(temp_queue[7:])
        else:
            pass
    except:
        return {'error': 'Unable to retrieve queue'}, 400
    return queue


@app.route('/add_song_to_queue', methods=['POST'])
def add_song_to_queue():
    '''
    Add a song to the queue
    '''
    # Get the song id from the request
    selected_song_index = int(request.form.get('selected_song', -1))
    if selected_song_index >= 0 and selected_song_index < len(songs):
        selected_song = songs[selected_song_index]
        # Add the selected song to the queue
        # Your queue management code here
        print(selected_song)
        # queue.append(selected_song)
        client.queue_song(selected_song)
        return {'message': 'Song added to the queue.'}, 200

    return {'error': 'Invalid song selection.'}, 400

if __name__ == '__main__':
    app.run(debug=True)