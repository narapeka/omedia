# OMEDIA Agent Notes

- Treat `.temp/` as the project-level scratch area for development-only artifacts.
- Use `scripts/dev.ps1 start` to run the backend and frontend during local development.
- Do not start FastAPI, Vite, or other long-running dev servers with ad hoc log files in `backend/`, `frontend/`, or the repository root.
- Captured dev server stdout/stderr belongs in `.temp/run-logs/`.
- Use `scripts/test-backend.ps1` for backend tests when practical so uv, pytest, and Python bytecode caches stay under `.temp/`.
- User/application runtime state belongs in `data/`: local config, SQLite databases, SQLite sidecars, and application logs.
- `data/common.yaml` is local-only and may contain secrets. Do not replace it with the example file.
