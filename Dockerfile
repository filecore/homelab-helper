FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ .

# Non-root user. GID 999 matches the docker group on most Linux hosts,
# giving the app access to the Docker socket without running as root.
RUN groupadd -g 999 docker-host \
    && useradd -r -u 1001 -g docker-host appuser \
    && mkdir -p /data \
    && chown -R appuser:docker-host /app /data

USER appuser

ENV CONFIG_PATH=/config/config.yaml
ENV STATE_FILE=/data/sandboxes.json

EXPOSE 7842

CMD ["gunicorn", "--workers", "1", "--bind", "0.0.0.0:7842", "wsgi:app"]
