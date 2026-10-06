# Backend Installation Notes

The backend requires several system dependencies to be installed via `brew` on macOS.

## System Dependencies

The following packages are required:
- `postgresql@16` (Database)
- `postgis` (Geospatial extension)
- `redis` (Caching and Task Queue)
- `rust` (Required for building Python packages like `pydantic-core`)

## Important Note on Installation Time

When installing these dependencies via Homebrew, you may notice a very large download for `llvm` (approx. 500MB+). This is a required dependency for `rust` and/or `postgresql` extensions in the Homebrew ecosystem.

Please be patient during the installation. Depending on your internet connection, this can take:
- Fast connection: 5-10 minutes
- Slower connection: 20-40 minutes

## Quick Start (after installation)

Once the system dependencies are installed:

1. **Start Services**:
   ```bash
   brew services start postgresql@16
   brew services start redis
   ```

2. **Install Python Dependencies**:
   ```bash
   cd backend
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Run Server**:
   ```bash
   uvicorn app.main:app --reload
   ```
