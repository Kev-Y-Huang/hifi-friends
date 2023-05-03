from flask import (
    Flask, 
    render_template, 
    request,
    Response
)
import client
import pyaudio
import socket
import os

HOST = socket.gethostname() # Server IP address
TCP_PORT = 1538 
UDP_PORT = 1539

BUFF_SIZE = 1024
CHUNK = 1024


app = Flask(__name__)

newClient = client.Client()

# Dummy list of songs
songs = os.listdir('server_files')

# Dummy queue of songs
queue = []


@app.route('/')
def index():
    return render_template('index.html', songs=songs, queue=queue)


def get_updated_songs():
    '''
    Function to ping the server and get the updated list of songs
    '''
    # temporarily return songs
    return songs


@app.route('/get_songs', methods=['GET'])
def get_songs():
    '''
    Flask route to update the list of songs, calls the get_updated_songs() function
    '''
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
        queue.append(selected_song)
        newClient.queue_song(selected_song)
        return {'message': 'Song added to the queue.'}, 200

    return {'error': 'Invalid song selection.'}, 400

if __name__ == '__main__':
    app.run(debug=True)
    newClient.run_client()