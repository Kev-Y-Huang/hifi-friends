document.addEventListener('DOMContentLoaded', () => {
    const form = document.querySelector('form');
    const audioPlayer = document.getElementById('audioPlayer');
    
    form.addEventListener('submit', (event) => {
      event.preventDefault();
      
      const selectedSong = form.elements.selected_song.value;
      const songUrl = "{{ songs[selectedSong-1].audio_url }}";
      
      audioPlayer.src = songUrl;
      audioPlayer.play();
    });
  });