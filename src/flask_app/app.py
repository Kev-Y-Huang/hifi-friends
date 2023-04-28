from flask import (
    Flask, 
    render_template, 
    request,
    Response
)
import pyaudio

# FORMAT = pyaudio.paInt16
# CHANNELS = 1
# RATE = 44100
# CHUNK = 1024
# RECORD_SECONDS = 5

# audio = pyaudio.PyAudio()
# stream = audio.open(
#     format=FORMAT, 
#     channels=CHANNELS, 
#     rate=RATE, 
#     input=True, 
#     frames_per_buffer=CHUNK
# )

app = Flask(__name__)

 
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
    pass


@app.route('/update_songs', methods=['GET'])
def update_songs():
    '''
    Flask route to update the list of songs
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
        file.save(f'./songs/{file}.wav')
        # Return a success message or relevant data
        return {'message': 'Song uploaded successfully.'}, 200

    # Return an error message if no file was uploaded
    return {'error': 'No song file uploaded.'}, 400


@app.route('/queue_song')
def queue_song():
    '''
    Add a song to the queue
    '''
    # Get the song id from the request
    song_id = request.args.get('song_id')
    # Get the song from the list of songs
    song = songs[song_id]
    # Add the song to the queue
    # queue.add(song)
    # Return a success message or relevant data

@app.route('/stream_audio')
def stream_audio():
    '''
    Stream song from the server
    '''
    # def generate_audio():
    #     while True:
    #         audio_data = stream.read(1024)
    #         yield (b'--frame\r\n'
    #                b'Content-Type: audio/wav\r\n\r\n' + audio_data + b'\r\n\r\n')

    # return Response(generate_audio(), mimetype='multipart/x-mixed-replace; boundary=frame')
    pass

if __name__ == '__main__':
    app.run(debug=True)