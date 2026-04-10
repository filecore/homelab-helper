# homelab-helper

A self-hosted web tool for trying out and deploying Docker services in a homelab. Generates Traefik v3 labels, AutoKuma monitor blocks, and Homepage dashboard entries.

Two main features:

- **Sandbox tab** - spin up any Docker image in a temporary container to try it out, then promote it directly into the service editor when you are happy with it.
- **New Service tab** - fill in a form and get a ready-to-paste docker-compose snippet with Traefik v3 labels, an AutoKuma monitor block, a Homepage dashboard entry, and a deployment checklist.

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
  auth_middleware: ""            # e.g. "tinyauth@file", "authelia@docker" - omit to hide auth toggle

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
  enabled: true
  network: "sandbox-net"         # dedicated network, separate from reverse-proxy
  cap_drop_all: true             # drop all Linux capabilities from sandbox containers
  no_new_privileges: true        # block privilege escalation via setuid binaries
  memory_limit: "512m"           # per-container memory cap (blank = no limit)
  cpu_limit: 1.0                 # per-container CPU cap in cores (0 = no limit)
  default_ttl_hours: 4
  max_sandboxes: 10
  ttl_options: [1, 4, 8, 24]

security:
  suppress_auth_warning: false   # set to true once the service is behind auth
```

## Sandbox feature

The sandbox tab lets you launch any Docker image as a temporary container. Containers expire automatically after the configured TTL.

When you are ready to add the service permanently, click **Promote** on the sandbox card. The editor opens pre-filled with the image, exposed port, and any non-system environment variables from the running container. Edit the fields and generate the compose snippet as normal.

Sandbox containers are run with `ALLOWED_HOSTS=*` injected automatically, which avoids host-validation errors in frameworks like Django.

## Security

homelab-helper is designed for trusted home networks and should not be exposed to the internet without authentication in front of it. The sections below describe the threat model and the mitigations in place.

### Authentication

homelab-helper has no built-in authentication. Anyone who can reach it on the network can launch arbitrary Docker containers and read your config.

Put it behind your reverse proxy with an auth middleware (TinyAuth, Authelia, etc.) before exposing it on your network. The UI displays a prominent warning banner until you set `security.suppress_auth_warning: true` in `config.yaml`.

### Docker socket access

The container mounts the Docker socket (`/var/run/docker.sock`), which gives the process root-equivalent control over the host. This is unavoidable for the sandbox feature to work. It means that if someone can reach the UI without authentication, they can run any container on your host.

This is not a reason to avoid the tool, but it is a reason to keep authentication in front of it and not expose port 7842 to the internet.

### Sandbox container isolation

The main risk of a sandbox feature is that a malicious or buggy image could be used to probe or attack other services on the same host. homelab-helper applies the following mitigations by default:

**Network isolation.** Sandbox containers are placed on a dedicated `sandbox-net` network rather than your production `reverse-proxy` network. Traefik is automatically connected to `sandbox-net` when the first sandbox is created, so FQDN routing still works. Containers on `sandbox-net` cannot reach other homelab services by container name.

**Capability dropping.** All Linux capabilities are dropped from sandbox containers (`cap_drop: ALL`). This prevents operations like binding to privileged ports, modifying network interfaces, or loading kernel modules.

**No privilege escalation.** The `no-new-privileges` security option blocks setuid binaries inside the container from gaining elevated privileges.

**Resource limits.** Each sandbox container is capped at 512 MB of memory and 1 CPU core by default, preventing a runaway container from exhausting host resources.

All four settings are configurable under `sandbox:` in `config.yaml`. Relaxing any of them shows an amber warning in the sandbox UI and in the setup wizard. The sandbox feature can be disabled entirely with `sandbox.enabled: false`.

### Shared service network

The New Service generator places all services on the shared Traefik network (default: `reverse-proxy`). Containers on the same Docker network can reach each other by container name on any port, including ports not published to the host. This is the standard Traefik homelab pattern and is acceptable for most home setups where all running services are trusted.

If you want stronger isolation between production services, the hardened pattern is to give each service its own internal network for talking to its database or sidecar, and attach it to `reverse-proxy` only for Traefik routing. This is a manual step outside the scope of the generator.
