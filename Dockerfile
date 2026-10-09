# Stage 1: Install dependencies with Poetry
FROM python:3.10-slim AS builder

# Environment settings
ENV POETRY_VERSION=1.8.3 \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install git, Poetry and tomli (needed by toml_deps.py before the venv exists)
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && pip install --no-cache-dir poetry==$POETRY_VERSION tomli==2.2.1 \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy dependencies first to cache them.
COPY pyproject.toml ./
COPY scripts/toml_deps.py ./scripts/toml_deps.py
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini ./
COPY .env-test .env

# Authenticate GitHub clones with the token from the host .npmrc.
# Passed as a BuildKit secret so the token is not copied into the image.
RUN --mount=type=secret,id=npmrc,target=/tmp/.npmrc <<'SH'
set -eu
token="$(sed -n 's#^//npm.pkg.github.com/:_authToken=##p' /tmp/.npmrc)"
if [ -z "$token" ]; then
    echo ".npmrc is missing //npm.pkg.github.com/:_authToken" >&2
    exit 1
fi
export GITHUB_PAT="$token"
export GIT_CONFIG_COUNT=1
export GIT_CONFIG_KEY_0="url.https://x-access-token:${token}@github.com/.insteadOf"
export GIT_CONFIG_VALUE_0="https://github.com/"
python -c 'from pathlib import Path; import re, poetry.utils.constants as constants; path = Path(constants.__file__); path.write_text(re.sub(r"(?m)^([A-Z_]*TIMEOUT)\s*=\s*\d+", r"\1 = 300", path.read_text()))'
/usr/local/bin/python scripts/toml_deps.py pyproject.toml /deps/exports
python -m venv .venv
poetry lock
poetry install --no-dev --no-interaction --no-ansi
SH

# Stage 2: Final lightweight image
FROM python:3.10-slim

# Set the working directory
WORKDIR /app

# Copy installed packages from the builder stage
COPY --from=builder /app /app
COPY prestart.sh worker-start.sh ./
RUN python -c "from pathlib import Path; [Path(name).write_bytes(Path(name).read_bytes().replace(bytes([13, 10]), bytes([10]))) for name in ('prestart.sh', 'worker-start.sh')]" \
    && chmod +x prestart.sh worker-start.sh \
    && mkdir -p /app/uploads

# Ensure SQLite database file persists as a volume
VOLUME ["/app/test.db"]

# Expose the application on port 8000
EXPOSE 8000

# Start the uvicorn
ENV PATH="/app/.venv/bin:$PATH"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
