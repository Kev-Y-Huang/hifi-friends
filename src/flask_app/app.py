from flask import (
    Flask, 
    render_template, 
    request,
    Response
)
from utils import client
import pyaudio
import socket

app = Flask(__name__)

# newClient = client.Client()

# Dummy list of songs
songs = [
    {
        'title': 'Song 1',
        'artist': 'Artist 1',
        'duration': '3:45',
        'audio_url': 'https://example.com/song1.mp3'
    },
    {
        'title': 'Song 2',
        'artist': 'Artist 2',
        'duration': '4:20',
        'audio_url': 'https://example.com/song2.mp3'
    }
]


# Dummy queue of songs
queue = [
    {
        'title': 'Song 1',
        'artist': 'Artist 1',
        'duration': '3:45',
        'audio_url': 'https://example.com/song1.mp3'
    },
]


@app.route('/')
def index():
    return render_template('index.html', songs=songs, queue=queue)


def get_updated_songs():
    '''
    Function to ping the server and get the updated list of songs
    '''
    # temporarily return songs
    return songs


@app.route('/update_songs', methods=['GET'])
def update_songs():
    '''
    Flask route to update the list of songs, calls the get_updated_songs() function
    '''
    pass


@app.route('/upload_song', methods=['POST'])
def upload_song():
    '''
    Flask route to upload a song to the server
    '''
    if 'file' in request.files:
        file = request.files['file']
        # Save the uploaded file to a desired location
        # file.save(f'./songs/{file}.wav')
        file.save(f'./songs/{file.filename}.wav')
        # Return a success message or relevant data
        return {'message': 'Song uploaded successfully.'}, 200

    # Return an error message if no file was uploaded
    return {'error': 'No song file uploaded.'}, 400


@app.route('/add_song_to_queue', methods=['POST'])
def add_song_to_queue():
    '''
    Add a song to the queue
    '''
    # Get the song id from the request
    song_id = request.args.get('song_id')
    # Get the song from the list of songs
    if not song_id:
        return {'error': 'No song id provided.'}, 400
    print(song_id)
    print(songs)
    song = songs[song_id]
    # Add the song to the queue
    queue.add(song)
    return {'message': 'Song added to queue successfully.'}, 200


# @app.route('/stream_audio')
# def stream_audio():
#     newClient.run_client(newClient)
#     # return app.response_class(generate_audio, mimetype='audio/x-wav')


p = pyaudio.PyAudio()
stream = p.open(
    format=p.get_format_from_width(2),
    channels=1,
    rate=44100,
    output=True
)


HOST = socket.gethostname() # Server IP address
TCP_PORT = 1538  # Server port
UDP_PORT = 1539

BUFF_SIZE = 65536
CHUNK = 10*1024

@app.route('/stream_audio')
def stream_audio():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
        client_socket.connect((HOST, TCP_PORT))
        print(f"Connected to server: {HOST}:{TCP_PORT}")

        client_socket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        client_socket.setsockopt(socket.SOL_SOCKET,socket.SO_RCVBUF,BUFF_SIZE)

        message = b'Hello'
        client_socket.sendto(message,(HOST, UDP_PORT))

        def generate_audio():
                while True:
                    audio_data = client_socket.recv(BUFF_SIZE)
                    if not audio_data:
                        break
                    yield audio_data

    return Response(generate_audio(), mimetype='audio/wav')
    
if __name__ == '__main__':
    app.run(debug=True)