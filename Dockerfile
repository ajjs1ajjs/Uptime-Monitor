# Multi-stage build for production (Go)
FROM golang:1.25-alpine AS builder

WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -ldflags="-s -w" -o /out/uptime-monitor ./cmd/uptime-monitor

FROM alpine:3.20

RUN apk add --no-cache ca-certificates iputils bind-tools \
    && addgroup -S uptime && adduser -S -G uptime uptime \
    && mkdir -p /data /config /logs \
    && chown -R uptime:uptime /data /config /logs

COPY --from=builder /out/uptime-monitor /usr/local/bin/uptime-monitor
COPY config.example.json /config/config.json
COPY README.md CHANGELOG.md ./

ENV CONFIG_PATH=/config/config.json \
    DATA_DIR=/data \
    LOG_DIR=/logs \
    DB_PATH=/data/sites.db

USER uptime

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://localhost:8080/health || exit 1

VOLUME ["/data", "/config", "/logs"]

LABEL maintainer="Uptime Monitor"
LABEL version="3.0.25"
LABEL description="Enterprise uptime & SSL monitoring (Go)"

CMD ["uptime-monitor", "server", "--config", "/config/config.json"]
