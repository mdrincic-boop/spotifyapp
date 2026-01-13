import json
import os
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
STATIONS_FILE = DATA_DIR / "stations.json"

SPOTIFY_SCOPES = "playlist-read-private playlist-read-collaborative"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class StationManager:
    def __init__(self, data_path: Path) -> None:
        self.data_path = data_path
        self.stations = []
        self.processes = {}
        self.streaming_mode = os.getenv("STREAMING_MODE", "mock")
        self.ffmpeg_path = os.getenv("FFMPEG_PATH", "ffmpeg")
        self.librespot_path = os.getenv("LIBRESPOT_PATH", "librespot")
        self.load()

    def load(self) -> None:
        if not self.data_path.exists():
            self.stations = []
            self.save()
            return
        self.stations = json.loads(self.data_path.read_text(encoding="utf-8"))
        for station in self.stations:
            station["status"] = "stopped"
            station["pid"] = None

    def save(self) -> None:
        self.data_path.write_text(
            json.dumps(self.stations, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def list_stations(self) -> List[Dict]:
        self.refresh_statuses()
        return self.stations

    def add_station(self, payload: Dict) -> Dict:
        station = {
            "id": str(uuid.uuid4()),
            "name": payload["name"],
            "playlist_id": payload["playlist_id"],
            "playlist_name": payload["playlist_name"],
            "port": int(payload["port"]),
            "mountpoint": payload["mountpoint"],
            "shoutcast": payload["shoutcast"],
            "status": "stopped",
            "pid": None,
            "created_at": utc_now(),
            "last_started": None,
        }
        self.stations.append(station)
        self.save()
        return station

    def get_station(self, station_id: str) -> Optional[Dict]:
        return next((station for station in self.stations if station["id"] == station_id), None)

    def refresh_statuses(self) -> None:
        if self.streaming_mode == "mock":
            return
        for station in self.stations:
            process = self.processes.get(station["id"])
            if process and process.poll() is not None:
                station["status"] = "stopped"
                station["pid"] = None
        self.save()

    def build_stream_command(self, station: Dict) -> List[str]:
        shoutcast = station["shoutcast"]
        stream_url = (
            f"icecast://{shoutcast['user']}:{shoutcast['password']}@"
            f"{shoutcast['host']}:{station['port']}/{station['mountpoint']}"
        )
        return [
            self.ffmpeg_path,
            "-re",
            "-i",
            "pipe:0",
            "-c:a",
            "libmp3lame",
            "-b:a",
            shoutcast["bitrate"],
            "-content_type",
            "audio/mpeg",
            "-f",
            "mp3",
            stream_url,
        ]

    def start_station(self, station: Dict) -> Dict:
        if station["status"] == "running":
            return station
        station["last_started"] = utc_now()
        if self.streaming_mode == "mock":
            station["status"] = "running"
            station["pid"] = None
            self.save()
            return station
        command = self.build_stream_command(station)
        process = subprocess.Popen(command, stdin=subprocess.PIPE)
        self.processes[station["id"]] = process
        station["status"] = "running"
        station["pid"] = process.pid
        self.save()
        return station

    def stop_station(self, station: Dict) -> Dict:
        if station["status"] != "running":
            return station
        process = self.processes.get(station["id"])
        if process:
            process.terminate()
            process.wait(timeout=10)
        station["status"] = "stopped"
        station["pid"] = None
        self.save()
        return station


app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key")
station_manager = StationManager(STATIONS_FILE)


def spotify_oauth() -> SpotifyOAuth:
    return SpotifyOAuth(
        client_id=os.getenv("SPOTIFY_CLIENT_ID"),
        client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
        redirect_uri=os.getenv("SPOTIFY_REDIRECT_URI"),
        scope=SPOTIFY_SCOPES,
        cache_handler=None,
        show_dialog=True,
    )


def get_spotify_client() -> Optional[Spotify]:
    token_info = session.get("token_info")
    if not token_info:
        return None
    oauth = spotify_oauth()
    if oauth.is_token_expired(token_info):
        token_info = oauth.refresh_access_token(token_info["refresh_token"])
        session["token_info"] = token_info
    return Spotify(auth=token_info["access_token"])


@app.route("/")
def index():
    return render_template("index.html", authenticated=bool(session.get("token_info")))


@app.route("/login")
def login():
    oauth = spotify_oauth()
    auth_url = oauth.get_authorize_url()
    return redirect(auth_url)


@app.route("/callback")
def callback():
    oauth = spotify_oauth()
    code = request.args.get("code")
    if not code:
        return redirect(url_for("index"))
    token_info = oauth.get_access_token(code)
    session["token_info"] = token_info
    return redirect(url_for("index"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/api/playlists")
def playlists():
    spotify_client = get_spotify_client()
    if spotify_client is None:
        return jsonify(
            {
                "authenticated": False,
                "playlists": [
                    {
                        "id": "demo-1",
                        "name": "Top Hits Demo",
                        "tracks": 50,
                        "image": "https://placehold.co/300x300?text=Playlist",
                    },
                    {
                        "id": "demo-2",
                        "name": "Chill Vibes Demo",
                        "tracks": 34,
                        "image": "https://placehold.co/300x300?text=Playlist",
                    },
                ],
            }
        )

    playlists = []
    results = spotify_client.current_user_playlists(limit=50)
    for item in results.get("items", []):
        image = item.get("images")
        playlists.append(
            {
                "id": item["id"],
                "name": item["name"],
                "tracks": item["tracks"]["total"],
                "image": image[0]["url"] if image else None,
            }
        )
    return jsonify({"authenticated": True, "playlists": playlists})


@app.route("/api/stations", methods=["GET", "POST"])
def stations():
    if request.method == "GET":
        return jsonify(station_manager.list_stations())
    payload = request.get_json(force=True)
    station = station_manager.add_station(payload)
    return jsonify(station), 201


@app.route("/api/stations/<station_id>/start", methods=["POST"])
def start_station(station_id: str):
    station = station_manager.get_station(station_id)
    if not station:
        return jsonify({"error": "Not found"}), 404
    station_manager.start_station(station)
    return jsonify(station)


@app.route("/api/stations/<station_id>/stop", methods=["POST"])
def stop_station(station_id: str):
    station = station_manager.get_station(station_id)
    if not station:
        return jsonify({"error": "Not found"}), 404
    station_manager.stop_station(station)
    return jsonify(station)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")), debug=True)
