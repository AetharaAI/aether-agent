# Aether Deployment Guide

**Version**: 3.0.0  
**Author**: Manus AI  
**Date**: February 1, 2026

## Overview

This guide provides comprehensive instructions for deploying Aether in various environments, from local development to production cloud deployments. It covers installation, configuration, deployment strategies, and operational best practices.

## Deployment Options

Aether supports multiple deployment strategies to accommodate different use cases and infrastructure requirements.

### Local Development

Local development deployment is ideal for testing, development, and single-user scenarios. This approach runs all components directly on the host machine without containerization. It provides fast iteration cycles, easy debugging access, and direct access to logs and processes. However, it requires manual dependency management and may have environment inconsistencies.

To deploy locally, ensure Redis Stack is installed and running on your system. Install Python 3.10 or higher with pip. Install Node.js 18 or higher with pnpm. Clone the Aether repository to your local machine. Copy `.env.template` to `.env` and configure your settings. Install Python dependencies with `pip install -r requirements.txt`. Navigate to the ui directory and install Node dependencies with `pnpm install`. Start all services with `./start_aether.sh`.

### Docker Compose

Docker Compose deployment is suitable for development teams, staging environments, and small production deployments. This approach containerizes all services with orchestration, providing consistent environments across machines, easy service management, and isolated dependencies. It requires Docker and Docker Compose installed but offers simplified deployment.

To deploy with Docker Compose, install Docker Engine and Docker Compose on your system. Clone the Aether repository. Copy `.env.template` to `.env` and configure your settings. Build and start services with `docker-compose up -d`. Verify all services are healthy with `docker-compose ps`. Access the UI at `http://localhost:3000` and the API at `http://localhost:8000`.

### Kubernetes

Kubernetes deployment is designed for production environments, high availability setups, and large-scale deployments. This approach provides horizontal scaling, automatic failover, and load balancing. It offers advanced orchestration features and cloud-native integration. However, it requires Kubernetes cluster access and more complex configuration.

To deploy on Kubernetes, create Kubernetes manifests for each service including deployments, services, and config maps. Set up persistent volumes for Redis data. Configure ingress for external access. Deploy with `kubectl apply -f k8s/`. Monitor with `kubectl get pods -n aether`.

### Cloud Platforms

Aether can be deployed on major cloud platforms with platform-specific configurations.

For AWS deployment, use ECS or EKS for container orchestration. Deploy ElastiCache for Redis. Use ALB for load balancing. Store secrets in AWS Secrets Manager. Configure CloudWatch for monitoring.

For Google Cloud Platform, use GKE for Kubernetes deployment. Deploy Cloud Memorystore for Redis. Use Cloud Load Balancing for traffic distribution. Store secrets in Secret Manager. Configure Cloud Monitoring for observability.

For Azure deployment, use AKS for Kubernetes orchestration. Deploy Azure Cache for Redis. Use Azure Load Balancer for distribution. Store secrets in Key Vault. Configure Azure Monitor for tracking.

## Prerequisites

Before deploying Aether, ensure the following prerequisites are met.

### System Requirements

The minimum system requirements depend on your deployment scale. For development environments, allocate 2 CPU cores, 4 GB RAM, and 10 GB disk space. For production environments, allocate 4 CPU cores, 8 GB RAM, and 50 GB disk space with SSD recommended for Redis.

### Software Dependencies

Required software includes Python 3.10 or higher, Redis Stack 7.0 or higher, and Node.js 18 or higher with pnpm. Optional software includes Docker 20.10 or higher, Docker Compose 2.0 or higher, and Kubernetes 1.24 or higher for cluster deployments.

### API Keys and Credentials

You will need an NVIDIA API key for Kimik2.5 access, which is required. Optional credentials include OpenClaw Fleet API key for multi-agent coordination, ASR service credentials for speech-to-text, and TTS service credentials for text-to-speech.

## Installation Steps

Follow these detailed steps to install Aether in your environment.

### Step 1: Obtain Aether

Download or clone the Aether repository to your deployment location. Extract the archive if downloaded as a compressed file. Navigate to the aether_project directory. Verify all files are present by checking for aether/, ui/, config/, docs/, and deployment scripts.

### Step 2: Configure Environment

Copy the environment template with `cp .env.template .env`. Edit the `.env` file with your preferred text editor. Set the required NVIDIA_API_KEY value. Configure Redis connection settings if not using defaults. Add optional API keys for Fleet, ASR, and TTS services. Save and close the file.

### Step 3: Install Dependencies

For Python dependencies, ensure pip is up to date with `pip install --upgrade pip`. Install required packages with `pip install -r requirements.txt`. Verify installation with `python -c "import fastapi, redis, aiohttp"`.

For UI dependencies, navigate to the ui directory. Install packages with `pnpm install`. Verify installation by checking that node_modules exists.

### Step 4: Configure Redis

For local Redis, install Redis Stack from the official website. Start Redis with `redis-server`. Verify it is running with `redis-cli ping`, which should return PONG. Optionally enable persistence by editing redis.conf to set `appendonly yes`.

For Docker Redis, the docker-compose.yml includes Redis configuration. Redis data persists in a Docker volume. Access RedisInsight at `http://localhost:8001` for management.

### Step 5: Start Services

For automated startup, run `./start_aether.sh` from the aether_project directory. The script will check prerequisites, start the API server, start the UI dev server, and display access URLs.

For Docker startup, run `docker-compose up -d` to start in detached mode. Check status with `docker-compose ps`. View logs with `docker-compose logs -f`.

For manual startup, start Redis with `redis-server`. Start the API server with `python -m aether.api_server`. In a new terminal, navigate to ui/ and start the UI with `pnpm dev`.

### Step 6: Verify Installation

Check the API health endpoint at `http://localhost:8000/health`, which should return status healthy. Access the UI at `http://localhost:3000` and verify the interface loads. Check that the status indicator shows "Online". Send a test message to verify the chat works. Review logs in the logs/ directory for any errors.

## Configuration

### Core Configuration

The `.env` file contains all core configuration settings.

#### Required Settings

`NVIDIA_API_KEY` is your NVIDIA API key for Kimik2.5 access. Obtain from the NVIDIA developer portal. This setting is required for agent functionality.

#### Redis Settings

`REDIS_HOST` defaults to localhost and specifies the Redis server hostname. Use the container name for Docker deployments. `REDIS_PORT` defaults to 6379 and specifies the Redis server port.

#### API Server Settings

`API_HOST` defaults to 0.0.0.0 and specifies the bind address for the API server. `API_PORT` defaults to 8000 and specifies the API server port.

### Optional Configuration

#### Fleet Integration

`FLEET_API_URL` specifies the OpenClaw Fleet API endpoint for multi-agent coordination. `FLEET_API_KEY` provides the authentication key for Fleet API access.

#### Voice Services

`VITE_ASR_ENDPOINT` defaults to `http://localhost:8001/asr` and specifies the speech-to-text service endpoint. `VITE_TTS_ENDPOINT` defaults to `http://localhost:8002/tts` and specifies the text-to-speech service endpoint.

For detailed voice service configuration, see the VOICE_SETUP.md guide.

#### UI Settings

`VITE_API_URL` defaults to `http://localhost:8000` and specifies the backend API URL for the UI. Use the appropriate URL for your deployment environment.

### Advanced Configuration

#### Redis Persistence

For production deployments, enable Redis persistence to prevent data loss.

Edit redis.conf to set `appendonly yes` for AOF persistence. Set `save 900 1` and `save 300 10` for RDB snapshots. Configure `appendfsync everysec` for balanced performance. Restart Redis to apply changes.

#### API Server Tuning

Adjust API server settings for your workload.

Set `WORKERS` environment variable to control Uvicorn workers. Configure `TIMEOUT` for request timeout limits. Adjust `MAX_CONNECTIONS` for concurrent connection limits. Enable `DEBUG=false` for production deployments.

#### Memory Limits

Configure Redis memory limits to prevent out-of-memory issues.

Set `maxmemory` in redis.conf to your desired limit. Configure `maxmemory-policy allkeys-lru` for eviction policy. Monitor memory usage with `redis-cli INFO memory`. Adjust limits based on usage patterns.

## Production Deployment

### Security Hardening

Implement these security measures for production deployments.

#### Network Security

Use HTTPS for all external connections with valid SSL certificates. Configure firewall rules to restrict access to necessary ports only. Use a reverse proxy like Nginx or Traefik for the UI. Enable CORS restrictions in the API server. Implement rate limiting to prevent abuse.

#### Authentication and Authorization

Implement API key authentication for API access. Use OAuth 2.0 for user authentication in the UI. Store credentials securely using secret management systems. Rotate API keys regularly. Implement role-based access control for multi-user scenarios.

#### Redis Security

Enable Redis authentication with `requirepass` in redis.conf. Use Redis ACLs for fine-grained access control. Enable SSL/TLS for Redis connections. Bind Redis to localhost or private network only. Disable dangerous commands like FLUSHALL in production.

#### Data Protection

Encrypt sensitive data at rest using Redis encryption. Encrypt data in transit with TLS. Implement backup and recovery procedures. Use secure environment variable management. Audit access logs regularly.

### High Availability

Ensure Aether remains available during failures.

#### Redis Clustering

Deploy Redis in cluster mode for horizontal scaling. Configure Redis Sentinel for automatic failover. Use Redis replication for data redundancy. Monitor cluster health continuously. Test failover procedures regularly.

#### API Server Scaling

Run multiple API server instances behind a load balancer. Use health checks for automatic instance management. Implement graceful shutdown procedures. Configure session affinity if needed. Monitor instance health and performance.

#### Database Backup

Schedule regular Redis backups using RDB or AOF. Store backups in a separate location or cloud storage. Test backup restoration procedures. Implement point-in-time recovery capabilities. Automate backup verification.

### Monitoring and Logging

Implement comprehensive monitoring for production systems.

#### Application Monitoring

Track API response times and error rates. Monitor WebSocket connection counts and stability. Measure memory usage and context statistics. Track agent task completion rates. Set up alerts for anomalies.

#### Infrastructure Monitoring

Monitor CPU and memory usage on all servers. Track disk I/O and network bandwidth. Monitor Redis performance metrics. Track container health in Docker/Kubernetes. Set up uptime monitoring for all services.

#### Logging

Centralize logs using a logging aggregation system like ELK stack or Splunk. Structure logs in JSON format for easy parsing. Implement log rotation to manage disk space. Set appropriate log levels for production. Retain logs according to compliance requirements.

### Performance Optimization

Optimize Aether for production workloads.

#### Caching

Implement response caching for frequent API calls. Use Redis for session caching. Cache static assets with appropriate headers. Implement CDN for UI assets. Monitor cache hit rates.

#### Database Optimization

Tune Redis configuration for your workload. Use pipelining for batch operations. Implement connection pooling. Monitor slow queries and optimize. Consider read replicas for read-heavy workloads.

#### Resource Management

Set appropriate resource limits in Docker/Kubernetes. Monitor and adjust based on actual usage. Implement auto-scaling policies. Use resource quotas to prevent overconsumption. Profile application performance regularly.

## Deployment Checklist

Use this checklist to ensure a complete deployment.

### Pre-Deployment

Verify all prerequisites are met. Review and update configuration files. Test in a staging environment. Prepare rollback procedures. Notify stakeholders of deployment schedule.

### Deployment

Back up existing data if upgrading. Deploy infrastructure changes first. Deploy application updates. Run database migrations if needed. Verify all services start successfully.

### Post-Deployment

Verify health checks pass for all services. Test critical user workflows. Monitor logs for errors. Check performance metrics. Confirm backup procedures are working.

### Ongoing Operations

Monitor system health continuously. Review logs daily for issues. Perform regular backups. Update dependencies regularly. Review and optimize performance monthly.

## Troubleshooting

### Deployment Issues

#### Services Won't Start

Check that all prerequisites are installed. Verify configuration files are correct. Check for port conflicts with `netstat -tulpn`. Review logs for error messages. Ensure environment variables are set correctly.

#### Connection Failures

Verify network connectivity between services. Check firewall rules allow necessary traffic. Confirm DNS resolution works correctly. Test with curl or telnet to verify connectivity. Review proxy and load balancer configurations.

#### Performance Problems

Monitor resource usage with top or htop. Check Redis memory usage and eviction. Review API response times in logs. Identify slow queries or operations. Scale resources as needed.

### Recovery Procedures

#### Service Restart

Stop all services gracefully. Verify processes have terminated. Start services in correct order (Redis, API, UI). Verify health checks pass. Test functionality after restart.

#### Data Recovery

Stop the affected service. Restore from the most recent backup. Verify data integrity after restoration. Restart services. Test functionality thoroughly.

#### Rollback

Stop the current deployment. Restore previous version from backup or version control. Restore database to previous state if needed. Restart services with previous configuration. Verify functionality.

## Maintenance

### Regular Maintenance Tasks

Perform these tasks regularly to maintain system health.

#### Daily Tasks

Review logs for errors and warnings. Check system resource usage. Verify backups completed successfully. Monitor API response times. Check for security alerts.

#### Weekly Tasks

Review performance metrics and trends. Update dependencies with security patches. Clean up old logs and temporary files. Test backup restoration procedures. Review and optimize slow queries.

#### Monthly Tasks

Perform comprehensive security audit. Review and update documentation. Analyze usage patterns and optimize. Plan capacity upgrades if needed. Review and update disaster recovery procedures.

### Updates and Upgrades

#### Updating Aether

Back up all data before updating. Review changelog for breaking changes. Test update in staging environment first. Apply updates during maintenance window. Verify functionality after update. Monitor for issues post-update.

#### Dependency Updates

Regularly update Python packages with `pip install --upgrade -r requirements.txt`. Update Node packages with `pnpm update`. Test thoroughly after updates. Review security advisories for dependencies. Keep Docker base images updated.

## Support

For deployment assistance, consult the main README_COMPLETE.md for general information. Review logs in the logs/ directory for error details. Check the troubleshooting section in this guide. Consult OpenClaw documentation for integration issues. Submit issues to the project repository with detailed information.

## Conclusion

This deployment guide provides comprehensive instructions for deploying Aether in various environments. Follow the appropriate sections for your deployment scenario, implement security best practices, and maintain regular monitoring and maintenance procedures to ensure a reliable and performant Aether installation.
