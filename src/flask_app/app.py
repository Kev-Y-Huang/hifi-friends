import subprocess
import os
import inspect
from flask import (
    Flask, 
    render_template, 
    request
)

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
    },
    {
        'title': 'Song 3',
        'artist': 'Artist 3',
        'duration': '2:55',
        'audio_url': 'https://example.com/song3.mp3'
    }
]

# def getSound(self):
#     # Current chunk of audio data
#     data = self.stream.read(self.CHUNK)
#     self.frames.append(data)
#     wave = self.save(list(self.frames))

#     return data


@app.route('/')
def index():
    return render_template('index.html', songs=songs)

@app.route('/play_song', methods=['POST'])
def play_song():
    selected_song = int(request.form['selected_song'])
    song_url = songs[selected_song - 1]['audio_url']
    return render_template('index.html', songs=songs, selected_song=selected_song, song_url=song_url)

if __name__ == '__main__':
    app.run(debug=True)