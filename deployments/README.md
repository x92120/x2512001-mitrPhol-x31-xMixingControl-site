# xMixing Architecture Deployments

This folder contains the localized node-specific `docker-compose` deployments based on the Hybrid Architecture strategy. Simply copy the corresponding YAML file to its target machine to spin up that node's required services. 

## How to Use:

### 1. General Dashboards (IPs: `192.168.121.21` & `.22`)
Copy `docker-compose.client.yml` to the target machine and run:
```bash
docker-compose -f docker-compose.client.yml up -d
```

### 2. Central Server (IP: `192.168.121.11`)
Copy `docker-compose.server.yml` to the central data proxy and run:
```bash
docker-compose -f docker-compose.server.yml up -d
```

### 3. Edge / Production Node (IP: `192.168.121.23`)
Copy `docker-compose.edge.yml` to the bridge machine monitoring the PLC and run:
```bash
docker-compose -f docker-compose.edge.yml up -d
```
