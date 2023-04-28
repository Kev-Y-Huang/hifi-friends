document.addEventListener("DOMContentLoaded", () => {
  const form = document.querySelector("form");
  const audioPlayer = document.getElementById("audioPlayer");

  form.addEventListener("submit", (event) => {
    event.preventDefault();

    const selectedSong = form.elements.selected_song.value;
    const songUrl = "{{ songs[selectedSong-1].audio_url }}";

    audioPlayer.src = songUrl;
    audioPlayer.play();
  });

  const uploadForm = document.getElementById("uploadForm");
  const fileInput = document.getElementById("fileInput");
  const messageDiv = document.getElementById("message");

  uploadForm.addEventListener("submit", (event) => {
    event.preventDefault();

    const file = fileInput.files[0];

    if (file) {
      const formData = new FormData();
      formData.append("file", file);

      fetch("/upload_song", {
        method: "POST",
        body: formData,
      })
        .then((response) => response.json())
        .then((data) => {
          messageDiv.textContent = data.message;
        })
        .catch((error) => {
          messageDiv.textContent = "An error occurred.";
          console.error("Error:", error);
        });
    } else {
      messageDiv.textContent = "Please select a file.";
    }
  });
});
