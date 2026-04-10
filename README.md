# homelab-helper

A self-hosted web tool for managing Docker services in a Traefik-based homelab.

Two main features:

- **Sandbox tab** — spin up any Docker image in a temporary container to try it out, then promote it directly into the service editor when you are happy with it.
- **New Service tab** — fill in a form and get a ready-to-paste docker-compose snippet with Traefik v3 labels, an AutoKuma monitor block, a Homepage dashboard entry, and a deployment checklist.

No deployment is performed. All output is copy-paste only.

## Requirements

- Docker (socket must be accessible to the container)
- Traefik v3 with a shared Docker network (default: `reverse-proxy`)
- Optionally: AutoKuma, Homepage dashboard

## Quick start

```
git clone https://github.com/filecore/homelab-helper
cd homelab-helper
docker compose up -d --build
```

Open `http://your-host:7842`. If no `config/config.yaml` exists, a first-run wizard will start automatically. It scans your Docker environment to pre-populate fields where possible, then writes the config file on completion.

To configure manually instead, copy the example and edit it:

```
cp config/config.example.yaml config/config.yaml
```

## docker-compose.yml

```yaml
services:
  homelab-helper:
    build: .
    container_name: homelab-helper
    restart: unless-stopped
    user: "1000:999"          # match your host user uid : docker group gid
    volumes:
      - ./config:/config
      - ./data:/data
      - /var/run/docker.sock:/var/run/docker.sock
    environment:
      - CONFIG_PATH=/config/config.yaml
      - STATE_FILE=/data/sandboxes.json
    ports:
      - "7842:7842"
    networks:
      - reverse-proxy

networks:
  reverse-proxy:
    external: true
```

The Docker socket mount is required for the sandbox feature. The `user` field should match the uid of the user that owns `./data` on the host, and the gid of the `docker` group (check with `stat /var/run/docker.sock`).

## config/config.yaml

```yaml
homelab:
  name: "My Homelab"

traefik:
  network: "reverse-proxy"       # Docker network shared between Traefik and containers
  entrypoint: "websecure"        # entryPoints name in traefik.yml (usually websecure)
  cert_resolver: "letsencrypt"   # certificatesResolvers name in traefik.yml
  auth_middleware: ""            # e.g. "tinyauth@file", "authelia@docker" — omit to hide auth toggle

domains:
  - example.com                  # first entry is the default in the form

autokuma:
  enabled: false                 # true if AutoKuma is running on your host

homepage:
  enabled: false                 # true if you use the Homepage dashboard
  groups:
    - Infrastructure
    - Monitoring
    - Media
    - Utilities

sandbox:
  default_ttl_hours: 4           # default expiry time for sandbox containers
  max_sandboxes: 10              # maximum concurrent sandboxes
  ttl_options: [1, 4, 8, 24]    # options shown in the TTL dropdown

security:
  suppress_auth_warning: false   # set to true once the service is behind auth
```

## Sandbox feature

The sandbox tab lets you launch any Docker image as a temporary container on a random host port. Containers expire automatically after the configured TTL.

When you are ready to add the service permanently, click **Promote** on the sandbox card. The editor opens pre-filled with the image, exposed port, and any non-system environment variables from the running container. Edit the fields and generate the compose snippet as normal.

Sandbox containers are run with `ALLOWED_HOSTS=*` injected automatically, which avoids host-validation errors in frameworks like Django.

## Security note

homelab-helper has access to the Docker socket and can launch arbitrary containers. It has no built-in authentication. Put it behind your reverse proxy with an auth middleware (TinyAuth, Authelia, etc.) before exposing it on your network.

Set `security.suppress_auth_warning: true` in `config.yaml` to dismiss the warning banner once auth is in place.
