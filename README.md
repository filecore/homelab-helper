# homelab-helper

A web wizard for adding Docker services to a Traefik-based homelab. Fill in a form, get a correct docker-compose snippet with Traefik v3 labels, an Uptime Kuma (AutoKuma) monitor block, and a Homepage dashboard entry.

No deployment is performed. Output is copy-paste only.

## Requirements

- Docker with a running Traefik v3 instance
- A shared Docker network (default: `reverse-proxy`)
- Optionally: AutoKuma and Homepage

## Setup

```
git clone https://github.com/filecore/homelab-helper
cd homelab-helper
cp config/config.yaml config/config.yaml   # edit to match your setup
docker compose up -d --build
```

Open `http://your-host:7842`.

## docker-compose.yml

```yaml
services:
  homelab-helper:
    build: .
    container_name: homelab-helper
    restart: unless-stopped
    volumes:
      - ./config:/config
    environment:
      - CONFIG_PATH=/config/config.yaml
    ports:
      - "7842:7842"
    networks:
      - reverse-proxy

networks:
  reverse-proxy:
    external: true
```

## config/config.yaml

```yaml
homelab:
  name: "My Homelab"

traefik:
  network: "reverse-proxy"
  cert_resolver: "cloudflare"
  entrypoint: "websecure"
  auth_middleware: "tinyauth@file"

domains:
  - example.com

autokuma:
  enabled: true

homepage:
  enabled: true
  groups:
    - Infrastructure
    - Monitoring
    - Media
    - Utilities
```

Set `auth_middleware` to an empty string or omit it to hide the auth option. Set `autokuma.enabled` or `homepage.enabled` to `false` to hide those sections.
