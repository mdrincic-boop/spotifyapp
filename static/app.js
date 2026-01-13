const playlistGrid = document.getElementById("playlist-grid");
const stationsGrid = document.getElementById("stations-grid");
const stationForm = document.getElementById("station-form");
const selectedPlaylistInput = document.getElementById("selected-playlist");
const activeStationsEl = document.getElementById("active-stations");
const playlistCountEl = document.getElementById("playlist-count");
const streamingModeEl = document.getElementById("streaming-mode");

let selectedPlaylist = null;

const state = {
  stations: [],
  playlists: [],
  authenticated: false,
};

function renderPlaylists() {
  playlistGrid.innerHTML = "";
  state.playlists.forEach((playlist) => {
    const card = document.createElement("div");
    card.className = "playlist-card";
    if (selectedPlaylist && selectedPlaylist.id === playlist.id) {
      card.classList.add("selected");
    }
    card.innerHTML = `
      <img class="playlist-cover" src="${playlist.image || "https://placehold.co/300x300?text=Playlist"}" alt="${playlist.name}" />
      <div class="playlist-meta">
        <h4>${playlist.name}</h4>
        <span>${playlist.tracks} pesama</span>
      </div>
    `;
    card.addEventListener("click", () => {
      selectedPlaylist = playlist;
      selectedPlaylistInput.value = playlist.name;
      renderPlaylists();
    });
    playlistGrid.appendChild(card);
  });
  playlistCountEl.textContent = state.playlists.length.toString();
}

function renderStations() {
  stationsGrid.innerHTML = "";
  state.stations.forEach((station) => {
    const card = document.createElement("div");
    card.className = "station-card";
    const statusClass = station.status === "running" ? "running" : "stopped";
    card.innerHTML = `
      <h3>${station.name}</h3>
      <p>${station.playlist_name}</p>
      <p>Port: ${station.port} • /${station.mountpoint}</p>
      <span class="station-status ${statusClass}">${station.status}</span>
      <div class="station-actions">
        <button class="button ${station.status === "running" ? "ghost" : "primary"}" data-action="start">Start</button>
        <button class="button ghost" data-action="stop">Stop</button>
      </div>
    `;
    card.querySelector('[data-action="start"]').addEventListener("click", () => handleStart(station.id));
    card.querySelector('[data-action="stop"]').addEventListener("click", () => handleStop(station.id));
    stationsGrid.appendChild(card);
  });
  const activeCount = state.stations.filter((station) => station.status === "running").length;
  activeStationsEl.textContent = activeCount.toString();
}

async function loadPlaylists() {
  const response = await fetch("/api/playlists");
  const data = await response.json();
  state.playlists = data.playlists;
  state.authenticated = data.authenticated;
  renderPlaylists();
}

async function loadStations() {
  const response = await fetch("/api/stations");
  state.stations = await response.json();
  renderStations();
}

async function handleStart(id) {
  await fetch(`/api/stations/${id}/start`, { method: "POST" });
  await loadStations();
}

async function handleStop(id) {
  await fetch(`/api/stations/${id}/stop`, { method: "POST" });
  await loadStations();
}

stationForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!selectedPlaylist) {
    alert("Prvo izaberi playlistu.");
    return;
  }
  const formData = new FormData(stationForm);
  const payload = {
    name: formData.get("name"),
    port: formData.get("port"),
    mountpoint: formData.get("mountpoint"),
    playlist_id: selectedPlaylist.id,
    playlist_name: selectedPlaylist.name,
    shoutcast: {
      host: formData.get("host"),
      user: formData.get("user"),
      password: formData.get("password"),
      bitrate: formData.get("bitrate"),
    },
  };
  await fetch("/api/stations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  stationForm.reset();
  selectedPlaylist = null;
  selectedPlaylistInput.value = "";
  await loadStations();
  await loadPlaylists();
});

async function bootstrap() {
  await Promise.all([loadPlaylists(), loadStations()]);
  setInterval(loadStations, 5000);
  fetch("/api/stations")
    .then((response) => response.json())
    .then((stations) => {
      if (stations.length > 0) {
        const mode = stations[0].pid ? "Live" : "Mock";
        streamingModeEl.textContent = mode;
      }
    });
}

bootstrap();
