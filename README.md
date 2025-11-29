# OMedia - Media Organizer

A media organizer application for normalizing media files according to Emby naming rules.

## Features

- **Share Link Import**: Paste 115 share links to save files with automatic media recognition
- **Manual Organize**: Select folders to batch organize with dry-run preview
- **Watchdog Monitoring**: Automatically organize new files using filesystem monitoring
- **115 Life Event Monitoring**: Monitor 115 cloud for new uploads
- **LLM + TMDB Recognition**: AI-powered media recognition with TMDB metadata lookup
- **Transfer Rules**: Configurable routing based on genre, country, language, and keywords
- **Naming Patterns**: Customizable folder and file naming with template variables
- **Multi-Storage Support**: 115 Cloud, Local filesystem, WebDAV

## Quick Start

### Docker (Recommended)

```bash
cd docker
cp .env.example .env
# Edit .env with your API keys and settings
docker-compose up -d
```

Access the app at http://localhost:8000

### Development Setup

**Backend:**
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

## Configuration

Set these environment variables (or create a `.env` file):

```bash
# LLM Configuration (OpenAI-compatible)
LLM_API_KEY=your-api-key
LLM_MODEL=gpt-4o-mini
LLM_BASE_URL=  # Optional, for custom endpoints

# TMDB Configuration
TMDB_API_KEY=your-tmdb-api-key

# 115 Cloud (get cookies from browser)
P115_COOKIES=your-115-cookies

# Storage Paths
P115_SHARE_RECEIVE_PATHS=["/我的接收/电影", "/我的接收/电视剧"]
STORAGE_LOCAL_MEDIA_PATHS=[]

# Optional: WebDAV
STORAGE_WEBDAV_URL=
STORAGE_WEBDAV_USERNAME=
STORAGE_WEBDAV_PASSWORD=
```

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Vue.js Frontend                    │
│  (ShareImport, ManualOrganize, Jobs, Settings)      │
└─────────────────────────────────────────────────────┘
                         │ REST API
┌─────────────────────────────────────────────────────┐
│                  FastAPI Backend                     │
├─────────────────────────────────────────────────────┤
│  Routers: share, organize, jobs, recognize, rules   │
├─────────────────────────────────────────────────────┤
│  Services: Recognizer, TransferEngine, Scheduler    │
├─────────────────────────────────────────────────────┤
│  VFS Layer: P115Adapter, WebDAVAdapter, LocalAdapter│
├─────────────────────────────────────────────────────┤
│  Event Bus (for extensibility hooks)                │
└─────────────────────────────────────────────────────┘
```

## Use Cases

### 1. Share Link Import
1. Copy a 115 share link
2. Open the app (clipboard auto-detected on mobile)
3. Review files and recognition result
4. Select target folder and save

### 2. Manual Organize
1. Browse to source folder
2. Select media type (Movie/TV)
3. Review dry-run report
4. Re-identify any incorrect items
5. Execute transfer

### 3. Watchdog Monitoring
1. Create a watchdog job for a local path
2. Set confidence threshold and auto-approve option
3. New files are automatically recognized and organized

### 4. 115 Life Event Monitoring
1. Create a life event job for a 115 cloud path
2. Monitor for uploads/moves
3. Auto-organize based on rules

## Transfer Rules

Rules match based on TMDB metadata and filename keywords:

```json
{
  "name": "Japanese Anime",
  "priority": 10,
  "media_type": "tv",
  "storage_type": "p115",
  "conditions": [
    {"field": "country", "operator": "in", "value": ["JP"]},
    {"field": "genre", "operator": "contains", "value": "Animation"}
  ],
  "target_path": "/Media/Anime/{title} ({year}) {tmdb-{tmdb_id}}"
}
```

## Naming Patterns

Template variables:
- `{title}` - Media title
- `{year}` - Release year
- `{tmdb_id}` - TMDB ID
- `{season:02d}` - Season number (padded)
- `{episode:02d}` - Episode number (padded)
- `{quality}` - Video quality
- `{version}` - Version tag

Example patterns:
- Movie: `{title} ({year}) {tmdb-{tmdb_id}}`
- TV Folder: `{title} ({year}) {tmdb-{tmdb_id}}`
- TV Episode: `{title} - S{season:02d}E{episode:02d}.{ext}`

## Mobile Support

The app includes Capacitor support for mobile deployment:
- Clipboard auto-detection on app focus
- Touch-optimized UI
- PWA-capable

## License

MIT

