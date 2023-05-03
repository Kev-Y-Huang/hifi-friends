function updateSongList() {
  fetch("/get_songs")
    .then((response) => response.json())
    .then((data) => {
      console.log("Response:", data);
      const songList = document.getElementById("songList");
      songList.innerHTML = "";
      data.forEach((song, index) => {
        const li = document.createElement("li");
        li.innerHTML = `
          <input
            type="radio"
            id="song${index + 1}"
            name="selected_song"
            value="${index}"
          />
          <label for="song${index + 1}">
            <h3>${song}</h3>
          </label>
        `;
        songList.appendChild(li);
      });
    })
    .catch((error) => {
      console.error("Error fetching song list:", error);
    });
}

// Function to update the queue
function updateQueue() {
  fetch("/get_queue")
    .then((response) => response.json())
    .then((data) => {
      const playingContainer = document.getElementById("playingContainer");
      const queueContainer = document.getElementById("queueContainer");

      if (data.length > 0) {
        playingContainer.innerHTML = `
          <label for="song1">
            <h3>${data[0]}</h3>
            <img
              id="playingIndicator"
              src="static/sound.gif"
              alt="Playing Indicator"
            />
          </label>
        `;
      } else {
        playingContainer.innerHTML = "<p>No song is currently playing.</p>";
      }

      const queueList = data.slice(1);
      const ul = document.createElement("ul");
      queueList.forEach((song, index) => {
        const li = document.createElement("li");
        li.innerHTML = `
          <label for="song${index + 2}">
            <h3>${song}</h3>
          </label>
        `;
        ul.appendChild(li);
      });

      queueContainer.innerHTML = "";
      queueContainer.appendChild(ul);
    })
    .catch((error) => {
      console.error("Error fetching queue:", error);
    });
}

// Add event listener to the upload form
document
  .getElementById("uploadForm")
  .addEventListener("submit", function (event) {
    event.preventDefault();

    const messageDiv = document.getElementById("message");
    const fileInput = document.getElementById("fileInput");
    const file = fileInput.files[0];
    const formData = new FormData();
    formData.append("file", file);

    fetch("/upload_song", {
      method: "POST",
      body: formData,
    })
      .then((response) => response.json())
      .then((data) => {
        messageDiv.textContent = data.error;
        updateSongList();
      })
      .catch((error) => {
        console.error("Error uploading song:", error);
      });
  });

// Add event listener to the "Add to Queue" button
document
  .getElementById("addToQueueButton")
  .addEventListener("click", function (event) {
    event.preventDefault()
    const selectedSongIndex = document.querySelector(
      'input[name="selected_song"]:checked'
    ).value;
    const formData = new FormData();
    formData.append("selected_song", selectedSongIndex);

    fetch("/add_song_to_queue", {
      method: "POST",
      body: formData,
    })
      .then((response) => response.json())
      .then((data) => {
        console.log("Response:", data);
        updateQueue();
      })
      .catch((error) => {
        console.error("Error adding song to queue:", error);
      });
  });

// Update the song list when the page loads
window.addEventListener("DOMContentLoaded", function () {
  updateSongList();
  updateQueue();
});

setInterval(function() {
  updateQueue();
}, 1000);


setInterval(function() {
  updateSongList();
}, 5000);