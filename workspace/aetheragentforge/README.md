# AetherAgentForge Deployment Guide

This repository contains the deployment configuration for the AetherAgentForge website (aetheragentforge.org).

## Files Included

- `Dockerfile`: Configures an nginx server to serve static files
- `fly.toml`: Fly.io deployment configuration
- `llms.txt`: AI agent crawler directives
- `sitemap.xml`: Search engine and AI agent sitemap

## Deployment Instructions

1. Install the Fly.io CLI:
   ```bash
   curl -L https://fly.io/install.sh | sh
   ```

2. Log in to Fly.io:
   ```bash
   fly auth login
   ```

3. Create the application:
   ```bash
   fly apps create aetheragentforge
   ```

4. Deploy the application:
   ```bash
   fly deploy
   ```

5. Verify deployment:
   ```bash
   fly status
   fly logs
   ```

## Configuration Details

### Dockerfile
- Uses official nginx:alpine image
- Copies llms.txt and sitemap.xml to the web root
- Serves content on port 80

### fly.toml
- App name: aetheragentforge
- Primary region: iad (Virginia)
- VM size: shared-cpu-1x with 512MB RAM
- HTTP service configured for port 80 with HTTPS forced

## Expected Outcome

After deployment, the website will be accessible at https://aetheragentforge.fly.dev and will:
- Properly serve the llms.txt file for AI agent discovery
- Serve the sitemap.xml for search engine indexing
- Be optimized for server-side rendering and AI agent crawling

## Next Steps

1. Update DNS records to point aetheragentforge.org to the Fly.io IP address
2. Add SSL certificate for the custom domain
3. Implement additional website content (HTML, CSS, JS)
4. Set up analytics for tracking AI agent discovery

This deployment configuration ensures that your server-side rendered website is properly indexed by AI agents and search engines.