document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("uploadForm");
  const audioPlayer = document.getElementById("audioPlayer");

  // add to queue
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

  const addToQueueButton = document.getElementById("addToQueueButton");
  addToQueueButton.addEventListener("click", () => {
    const selectedSong = document.querySelector(
      'input[name="selected_song"]:checked'
    );

    if (selectedSong) {
      const selectedSongValue = selectedSong.value;

      fetch("/add_song_to_queue", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ selectedSong: selectedSongValue }),
      })
        .then((response) => response.json())
        .then((data) => {
          console.log(data);
          // Handle the response data as needed
          if (data.message) {
            // Update the queue on the webpage
            const queueContainer = document.getElementById("queueContainer");
            const newSongElement = document.createElement("li");
            newSongElement.innerHTML = `
              <label>
                <h3>${data.song.title}</h3>
                <p>${data.song.artist} - ${data.song.duration}</p>
              </label>
            `;
            queueContainer.appendChild(newSongElement);
          } else {
            // Handle the error case
            console.error("Error:", data.error);
          }
        })
        .catch((error) => {
          console.error("Error:", error);
        });
    } else {
      // Handle the case when no song is selected
    }
  });

  fetch("/stream_audio")
    .then((response) => {
      const reader = response.body.getReader();

      return new ReadableStream({
        start(controller) {
          function push() {
            reader.read().then(({ done, value }) => {
              if (done) {
                controller.close();
                return;
              }

              controller.enqueue(value);
              push();
            });
          }

          push();
        },
      });
    })
    .then((stream) => new Response(stream))
    .then((response) => response.blob())
    .then((blob) => {
      console.log(blob);
      const objectUrl = URL.createObjectURL(blob);
      audioPlayer.src = objectUrl;
      audioPlayer.play();
    })
    .catch((error) => {
      console.error("Error streaming audio:", error);
    });
});
