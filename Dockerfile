# Keep this file to what a local run on another machine needs.
FROM python:3.13-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .
COPY scripts ./scripts

# Run as a normal user, not root.
RUN useradd --create-home library
USER library

EXPOSE 8000

# Bring the database up to date, then start the API.
CMD ["sh", "-c", "python -m library_api.migrate && exec uvicorn library_api.app:create_app --factory --host 0.0.0.0 --port 8000"]
