# JetStream Super Cluster Build Specification

## Architecture Overview

A JetStream Super Cluster is a distributed messaging system designed for high availability, scalability, and fault tolerance across multiple regions or data centers. The architecture consists of multiple NATS clusters connected via gateways, with JetStream enabled for persistent messaging.

### Key Components

- **Clusters**: Groups of NATS servers within a single data center/region
- **Gateways**: Connections between clusters that enable cross-cluster message routing
- **JetStream**: Persistent message storage with replication and durability
- **Meta/API Layer**: A RAFT-based leadership system that handles stream/consumer placement

## Deployment Requirements

### Minimum Configuration

- At least 3 clusters in the supercluster (for RAFT quorum)
- Minimum 3 nodes per cluster (for R3 stream replication)
- Odd number of servers across the entire supercluster
- Dedicated network for cluster communication (separate from client traffic)
- Fast SSD storage for JetStream data persistence

### Network Configuration

```
# Cluster internal communication (for RAFT consensus)
listen: 10.10.151.212:5222
routes: [
  "nats-route://cluster1-node1:5222",
  "nats-route://cluster1-node2:5222",
  "nats-route://cluster1-node3:5222"
]

# Gateway connections between clusters
gateway: {
  name: "cluster1"
  listen: 10.10.151.212:7222
  reject_unknown: true
  gateways: [
    {"name": "cluster1", "urls": ["nats://cluster1-node1:7222", "nats://cluster1-node2:7222", "nats://cluster1-node3:7222"]},
    {"name": "cluster2", "urls": ["nats://cluster2-node1:7222", "nats://cluster2-node2:7222", "nats://cluster2-node3:7222"]},
    {"name": "cluster3", "urls": ["nats://cluster3-node1:7222", "nats://cluster3-node2:7222", "nats://cluster3-node3:7222"]}
  ]
}
```

## JetStream Configuration

### Stream Placement

Use placement tags to control where streams are replicated:

- Place streams across different availability zones within a region
- Use "stretch clusters" (nodes in different regions) for immediate consistency between regions
- Avoid placing replicas on servers within the same availability zone

### Resource Management

```
jetstream: {
  # Maximum memory allocation for JetStream
  max_memory: "16GB"
  
  # Maximum storage allocation for JetStream
  max_storage: "200GB"
  
  # Storage directory (use SSD)
  store_dir: "/data/jetstream"
  
  # Stream defaults
  max_streams: 1000
  max_consumers: 10000
}
```

## Monitoring and Management

### Monitoring Endpoints

Enable the NATS HTTP monitoring server:

```
http_port: 8222
```

#### Critical Monitoring Endpoints

| Endpoint | Purpose | Key Metrics |
|----------|---------|-------------|
| `/varz` | Server health | Memory usage, connections, subscriptions, throughput |
| `/connz` | Client connections | Active connections, pending messages, idle time |
| `/routez` | Cluster routes | Route status, latency, message rates |
| `/gatewayz` | Inter-cluster connections | Gateway status, latency, message rates |
| `/jsz` | JetStream status | Streams, consumers, storage usage, API errors |
| `/healthz` | Liveness check | Server availability, JetStream enabled status |

### Monitoring Commands

```
# List all servers in the cluster
nats server list -s nats://cluster1-node1:4222

# Get detailed JetStream cluster status
nats server report jetstream -s nats://cluster1-node1:4222

# View active connections
nats server report connections -s nats://cluster1-node1:4222

# Check cluster health
nats server report -s nats://cluster1-node1:4222

# Real-time monitoring
nats-top -s nats://cluster1-node1:4222
```

### Key Metrics to Monitor

1. **Resource Usage**:
   - `reserved_mem` and `reserved_store` - JetStream resource reservations
   - Total streams and consumers
   - Memory and storage utilization

2. **Performance**:
   - `in_msgs`/`out_msgs` - Message throughput rates
   - `in_bytes`/`out_bytes` - Data transfer rates
   - `slow_consumers` - Backpressure indicators
   - Connection idle times

3. **Health**:
   - RAFT consensus status
   - Stream lag and consumer throughput
   - API error rates (often from misconfigured clients)
   - Uptime metrics (detect silent restarts)

4. **Connectivity**:
   - Gateway connection status
   - Route latency and message rates
   - Cluster membership changes

### Alerting Thresholds

- Alert when memory utilization > 80%
- Alert when storage utilization > 85%
- Alert when slow consumers > 5 for more than 5 minutes
- Alert when RAFT leader changes occur
- Alert when gateway connections drop
- Alert when stream lag exceeds 1000 messages for more than 1 minute

## Security Configuration

### Authentication and Authorization

```
# Enable authentication
authorization: {
  # Use JWT for service accounts
  users: [
    {user: "service", password: "secure_password_1"},
    {user: "admin", password: "secure_password_2"}
  ]
}

# Implement TLS for all connections
tls: {
  cert_file: "/etc/nats/certs/server-cert.pem"
  key_file: "/etc/nats/certs/server-key.pem"
  ca_file: "/etc/nats/certs/ca.pem"
  timeout: 2
}
```

### Network Security

- Use network policies to restrict access to monitoring endpoints (port 8222)
- Implement firewall rules to allow only trusted IP addresses to access cluster ports (5222, 7222)
- Never expose monitoring endpoints to public internet
- Use TLS for all connections (client and cluster)

## Backup and Disaster Recovery

### Data Backup Strategy

- Daily backups of JetStream store directory (`/data/jetstream`)
- Store backups in geographically separate location
- Test backup restoration quarterly
- Implement incremental backups for large datasets

### Disaster Recovery Plan

1. **Cluster Failure**:
   - Auto-recovery handles single node failures
   - Manual intervention required for multi-node failures
   - Restore from backup if data is irrecoverable

2. **Gateway Failure**:
   - Clusters continue operating independently
   - Messages queue until gateway is restored
   - Monitor backlog and increase bandwidth if needed

3. **Full Supercluster Failure**:
   - Restore from latest backup
   - Reconfigure cluster topology
   - Re-establish gateway connections
   - Validate stream integrity

## Operational Best Practices

### Daily Operations

- Monitor monitoring endpoints daily
- Review logs for errors and warnings
- Check resource utilization trends
- Verify backup integrity
- Test failover procedures

### Maintenance Windows

- Schedule maintenance during low-traffic periods
- Drain connections gracefully before maintenance
- Monitor cluster quorum during maintenance
- Validate functionality after maintenance

### Scaling Strategy

- Horizontal scaling: Add more nodes to existing clusters
- Vertical scaling: Increase resources on existing nodes
- Cluster expansion: Add new clusters to the supercluster
- Use placement tags to distribute load evenly

## Monitoring Dashboard Configuration

### Prometheus Configuration

```
scrape_configs:
  - job_name: 'nats-cluster'
    static_configs:
      - targets: ['cluster1-node1:8222', 'cluster1-node2:8222', 'cluster1-node3:8222',
                  'cluster2-node1:8222', 'cluster2-node2:8222', 'cluster2-node3:8222',
                  'cluster3-node1:8222', 'cluster3-node2:8222', 'cluster3-node3:8222']
    metrics_path: '/varz'
    scrape_interval: 15s

  - job_name: 'nats-jetstream'
    static_configs:
      - targets: ['cluster1-node1:8222', 'cluster1-node2:8222', 'cluster1-node3:8222',
                  'cluster2-node1:8222', 'cluster2-node2:8222', 'cluster2-node3:8222',
                  'cluster3-node1:8222', 'cluster3-node2:8222', 'cluster3-node3:8222']
    metrics_path: '/jsz'
    scrape_interval: 15s
```

### Grafana Dashboard Recommendations

1. **Cluster Health Overview**:
   - Number of active clusters and nodes
   - Gateway connection status
   - RAFT leader status
   - System uptime

2. **Resource Utilization**:
   - Memory usage per cluster
   - Storage usage per cluster
   - Message throughput (msgs/sec)
   - Data transfer rates (MB/sec)

3. **Stream and Consumer Metrics**:
   - Number of active streams
   - Number of active consumers
   - Stream lag
   - Consumer throughput
   - Consumer backpressure

4. **Connection Metrics**:
   - Total active connections
   - Connections by client type
   - Connection idle times
   - Reconnection rates

5. **Error Monitoring**:
   - API error rates
   - Authentication failures
   - Connection timeouts
   - JetStream storage errors

## Automation and Self-Service

### Automated Validation

- Implement automated tests to validate stream integrity after deployment
- Create self-service pipelines for:
  - Requesting new streams
  - Creating consumers
  - Getting credentials
  - Monitoring health
- Implement automated alerts for:
  - Resource exhaustion
  - Performance degradation
  - Connectivity issues

### Documentation and Training

- Create comprehensive documentation on:
  - Cluster architecture
  - Monitoring procedures
  - Troubleshooting guide
  - Backup and recovery
  - Scaling procedures
- Conduct training sessions for:
  - Operations teams
  - Development teams
  - Security teams

## Troubleshooting Guide

### Common Issues and Solutions

| Issue | Symptoms | Solution |
|-------|----------|----------|
| Cluster split-brain | Multiple leaders, data inconsistency | Ensure odd number of nodes, check network connectivity |
| JetStream storage full | New messages rejected, streams paused | Increase storage limits, purge old data, add more nodes |
| Gateway connection failure | Cross-cluster messages not delivered | Check firewall rules, network connectivity, gateway configuration |
| Slow consumers | Backpressure, message buildup | Increase consumer processing capacity, optimize consumer code |
| RAFT leader election failure | Streams unavailable, API errors | Check cluster connectivity, ensure proper quorum, verify server health |
| Authentication failures | Clients cannot connect | Verify credentials, check TLS certificates, validate JWT tokens |
| High latency | Slow message delivery | Optimize network paths, reduce geographic distance, use local clusters |

### Debug Commands

```
# Check server status
nats server info -s nats://cluster1-node1:4222

# Check JetStream status
nats server report jetstream -s nats://cluster1-node1:4222

# List all streams
nats stream list -s nats://cluster1-node1:4222

# View consumer details
nats consumer list <stream_name> -s nats://cluster1-node1:4222

# Check connection details
nats conn list -s nats://cluster1-node1:4222

# Get detailed network information
nats server report -s nats://cluster1-node1:4222
```

## Conclusion

This JetStream Super Cluster build specification provides a comprehensive framework for deploying a highly available, scalable, and observable messaging infrastructure. By following these guidelines, organizations can ensure their messaging backbone meets the demands of modern distributed applications while maintaining operational resilience and security.

Key success factors:
- Proper cluster topology with quorum and redundancy
- Comprehensive monitoring and alerting
- Robust security configuration
- Automated operations and self-service capabilities
- Well-documented procedures and training

Regular review and refinement of this specification should be conducted as technology and requirements evolve.