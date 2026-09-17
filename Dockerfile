# Uptime Monitor — multi-stage Dockerfile (OPS-001).
#
# Build:   docker build -t uptime-monitor:local .
# Run:     docker run -d --name uptime-monitor -p 8080:8080 \
#              -v uptime-data:/var/lib/uptime-monitor \
#              -v uptime-config:/etc/uptime-monitor \
#              uptime-monitor:local
#
# The binary is fully static (modernc.org/sqlite is pure Go, CGO disabled),
# so the runtime image is a minimal Alpine with only CA certs + tzdata.

FROM golang:1.26-alpine3.24 AS builder
WORKDIR /src

# Leverage layer caching: dependencies first.
COPY go.mod go.sum ./
RUN go mod download

COPY . .
# Static binary, stripped symbol tables / DWARF for a smaller image.
RUN CGO_ENABLED=0 go build -ldflags="-s -w" -o /out/uptime-monitor ./cmd/uptime-monitor

FROM alpine:3.24
RUN apk add --no-cache ca-certificates tzdata \
    && addgroup -S uptime && adduser -S uptime -G uptime \
    && mkdir -p /var/lib/uptime-monitor /etc/uptime-monitor \
    && chown -R uptime:uptime /var/lib/uptime-monitor /etc/uptime-monitor

COPY --from=builder /out/uptime-monitor /usr/local/bin/uptime-monitor

# Writable at runtime: database/backups (DATA_DIR) + config (CONFIG_PATH dir).
VOLUME ["/var/lib/uptime-monitor", "/etc/uptime-monitor"]
EXPOSE 8080

ENV CONFIG_PATH=/etc/uptime-monitor/config.json \
    DB_PATH=/var/lib/uptime-monitor/sites.db

USER uptime:uptime
ENTRYPOINT ["/usr/local/bin/uptime-monitor", "server", "--config", "/etc/uptime-monitor/config.json"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://127.0.0.1:8080/health/ready || exit 1
