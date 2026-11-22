# Keep this file to what a local run on another machine needs.
FROM python:3.13-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

CMD ["python", "-c", "import project_name; print(project_name.__version__)"]
