# ThingsBoard Community Edition (Docker)

This directory contains the Docker configuration for ThingsBoard.

## Port Mapping
- **Web UI:** [http://localhost:9090](http://localhost:9090)
- **MQTT:** Port `1884` (Mapped from internal 1883 to avoid conflict with RabbitMQ)
- **CoAP:** Port `5683`

## How to Start
```bash
cd /home/x-root/xApp/x2512001-mitrPhol-x31-xMixingControl/x3194-ThingsBoard
docker compose up -d
```

## Default Credentials
- **System Administrator:** `sysadmin@thingsboard.org` / `sysadmin`
- **Tenant Administrator:** `tenant@thingsboard.org` / `tenant`
- **Customer User:** `customer@thingsboard.org` / `customer`

## Data Persistence
- Database and configuration data are stored in `./mytb-data`.
- Logs are stored in `./mytb-logs`.
