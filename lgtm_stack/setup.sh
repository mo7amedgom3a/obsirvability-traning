#!/usr/bin/env bash

set -e

echo "======================================================================="
echo " Starting Full Observability Stack Deployment (Host + Docker Hybrid)"
echo "======================================================================="

# 1. Install Docker & Docker Compose if missing
if ! command -v docker &> /dev/null; then
    echo "[*] Installing Docker..."
    sudo dnf install -y docker || sudo apt-get update && sudo apt-get install -y docker.io
    sudo systemctl enable --now docker
    sudo usermod -aG docker $USER
fi

if ! docker compose version &> /dev/null; then
    echo "[*] Installing Docker Compose Plugin..."
    sudo dnf install -y docker-compose-plugin || sudo apt-get install -y docker-compose-plugin
fi

# 2. Stop and clean up legacy host-level observability services to avoid port clashes
echo "[*] Ensuring legacy host-level observability services are disabled..."
sudo systemctl stop alloy loki tempo prometheus node_exporter 2>/dev/null || true
sudo systemctl disable alloy loki tempo prometheus node_exporter 2>/dev/null || true

# 3. Create host-level directories for configurations
echo "[*] Creating configuration spaces..."
sudo mkdir -p /etc/prometheus /var/lib/prometheus
WORKDIR=$(pwd)

# 4. Install Prometheus Natively on the Host
if ! command -v prometheus &> /dev/null; then
    echo "[*] Installing Prometheus natively via binary..."
    PROM_VERSION="2.51.1"
    curl -LO "https://github.com/prometheus/prometheus/releases/download/v${PROM_VERSION}/prometheus-${PROM_VERSION}.linux-amd64.tar.gz"
    tar -xf prometheus-${PROM_VERSION}.linux-amd64.tar.gz
    sudo cp "prometheus-${PROM_VERSION}.linux-amd64/prometheus" /usr/local/bin/
    sudo cp "prometheus-${PROM_VERSION}.linux-amd64/promtool" /usr/local/bin/
    rm -rf prometheus-${PROM_VERSION}.linux-amd64*
fi

# 5. Install Node Exporter Natively on the Host
if ! command -v node_exporter &> /dev/null; then
    echo "[*] Installing Node Exporter natively via binary..."
    NODE_VERSION="1.7.0"
    curl -LO "https://github.com/prometheus/node_exporter/releases/download/v${NODE_VERSION}/node_exporter-${NODE_VERSION}.linux-amd64.tar.gz"
    tar -xf node_exporter-${NODE_VERSION}.linux-amd64.tar.gz
    sudo cp "node_exporter-${NODE_VERSION}.linux-amd64/node_exporter" /usr/local/bin/
    rm -rf node_exporter-${NODE_VERSION}.linux-amd64*
fi

# 6. Write Host Systemd Service Units
echo "[*] Configuring systemd units for host components..."

cat <<EOF | sudo tee /etc/systemd/system/node_exporter.service
[Unit]
Description=Node Exporter
After=network.target

[Service]
User=root
ExecStart=/usr/local/bin/node_exporter
Restart=always

[Install]
WantedBy=multi-user.target
EOF

cat <<EOF | sudo tee /etc/systemd/system/prometheus.service
[Unit]
Description=Prometheus Time Series Database
After=network.target

[Service]
User=root
ExecStart=/usr/local/bin/prometheus \\
  --config.file=/etc/prometheus/prometheus.yml \\
  --storage.tsdb.path=/var/lib/prometheus/
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# 7. Write Native Prometheus Configuration File
cat <<EOF | sudo tee /etc/prometheus/prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: "node_exporter"
    static_configs:
      - targets: ["localhost:9100"]

  - job_name: "prometheus"
    static_configs:
      - targets: ["localhost:9090"]
EOF

# 8. Reload systemd and start Host Monitors
sudo systemctl daemon-reload
sudo systemctl enable --now node_exporter prometheus

# 9. Build local configurations for Docker Compose Pipeline
echo "[*] Generating containerized pipeline configurations..."

cat <<EOF > "${WORKDIR}/tempo.yaml"
server:
  http_listen_port: 3200
  grpc_listen_port: 3201

distributor:
  receivers:
    otlp:
      protocols:
        http:
          endpoint: 0.0.0.0:4328
        grpc:
          endpoint: 0.0.0.0:4327

compactor:
  compaction:
    compaction_window: 1h
    max_block_bytes: 100000000
    block_retention: 24h
    compacted_block_retention: 1h

storage:
  trace:
    backend: local
    wal:
      path: /tmp/tempo/wal
    local:
      path: /tmp/tempo/blocks

metrics_generator:
  registry:
    external_labels:
      source: tempo
  storage:
    path: /tmp/tempo/generator/wal
    remote_write:
      - url: http://mimir:9009/api/v1/push
        send_exemplars: true
  processor:
    service-graphs: {}
    span-metrics: {}

overrides:
  defaults:
    metrics_generator:
      processors: [service-graphs, span-metrics]
EOF

cat <<EOF > "${WORKDIR}/config.alloy"
loki.write "local" {
  endpoint {
    url = "http://loki:3100/loki/api/v1/push"
  }
}

discovery.docker "linux" {
  host = "unix:///var/run/docker.sock"
}

discovery.relabel "docker_logs" {
  targets = discovery.docker.linux.targets
  rule {
    source_labels = ["__meta_docker_container_name"]
    regex         = "/(.*)"
    target_label  = "container"
  }
}

loki.source.docker "default" {
  host       = "unix:///var/run/docker.sock"
  targets    = discovery.relabel.docker_logs.output
  forward_to = [loki.process.parse_json.receiver]
}

loki.process "parse_json" {
  forward_to = [loki.write.local.receiver]
  stage.json {
    expressions = {
      level       = "level",
      event       = "event",
      status_code = "status_code",
      request_id  = "request_id",
      http_path   = "http_path",
    }
  }
  stage.labels {
    values = {
      level = "",
    }
  }
}

otelcol.receiver.otlp "default" {
  grpc { endpoint = "0.0.0.0:4317" }
  http { endpoint = "0.0.0.0:4318" }
  output {
    traces = [otelcol.exporter.otlp.tempo.input]
  }
}

otelcol.exporter.otlp "tempo" {
  client {
    endpoint = "tempo:4327"
    tls {
      insecure             = true
      insecure_skip_verify = true
    }
  }
}
EOF

# 10. Start the Containerized Engine
echo "[*] Launching containerized stack via Docker Compose..."
docker compose up -d --build

echo "======================================================================="
echo " Deployment Finished Successfully!"
echo " - Prometheus Server: http://localhost:9090"
echo " - Node Exporter:      http://localhost:9100"
echo " - Loki Engine:        http://localhost:3100"
echo " - Tempo Engine:       http://localhost:3200"
echo " - Alloy OTLP Mesh:    Ports 4317 (gRPC) & 4318 (HTTP)"
echo "======================================================================="