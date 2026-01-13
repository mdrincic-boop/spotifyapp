# Spotify Radio Control Center

Profesionalna Flask aplikacija za upravljanje Spotify radio stanicama koje se streamuju na Shoutcast servere. Aplikacija podržava više simultanih stanica, persistenciju konfiguracije i moderan tamni UI.

## Funkcionalnosti

- Spotify OAuth2 login i pregled playlisti
- Kreiranje više radio stanica na različitim portovima
- Start/Stop kontrole i real-time status
- Persistencija konfiguracije u JSON fajlu
- Moderni dashboard sa karticama i animacijama

## Instalacija

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Konfiguracija

Kreiraj `.env` fajl u root direktorijumu:

```bash
FLASK_SECRET_KEY=promeni_me
SPOTIFY_CLIENT_ID=spotify_client_id
SPOTIFY_CLIENT_SECRET=spotify_client_secret
SPOTIFY_REDIRECT_URI=http://localhost:8000/callback
STREAMING_MODE=mock
FFMPEG_PATH=ffmpeg
LIBRESPOT_PATH=librespot
```

> `STREAMING_MODE=mock` je podrazumevano. Kada integrišeš FFmpeg + librespot pipeline, postavi `STREAMING_MODE=live`.

## Pokretanje

```bash
source .venv/bin/activate
python app.py
```

Aplikacija će biti dostupna na `http://localhost:8000` i dostupna na mreži preko `http://<ipv4>:8000`.

## Streaming integracija

U `STREAMING_MODE=live` režimu, aplikacija očekuje da šalješ audio u FFmpeg preko `stdin` (npr. kroz librespot ili custom player). Primer pipeline:

```bash
librespot --name "Radio1" --backend pipe --emit-sink - | \
  ffmpeg -re -i pipe:0 -c:a libmp3lame -b:a 192k -content_type audio/mpeg -f mp3 icecast://source:password@host:9001/stream
```

## Troubleshooting

- **Login ne radi:** Proveri Spotify redirect URI i da li je Premium nalog.
- **Nema zvuka:** Proveri da li je FFmpeg instaliran i da li Shoutcast prihvata mountpoint.
- **Stanice se ne vide nakon restarta:** Proveri `data/stations.json` dozvole.
- **CORS ili mrežni pristup:** Flask već sluša na `0.0.0.0`.

## Potencijalna poboljšanja

- WebSocket status i log streaming
- Automatsko preuzimanje cover art po stanicama
- Scheduler i smart shuffle logika
- Admin role i multi-user podrška
- Docker compose za FFmpeg + librespot
