# Multi-stage build for Aether UI

# Stage 1: Build
FROM node:20-alpine AS builder

WORKDIR /app

# Install pnpm
RUN corepack enable && corepack prepare pnpm@latest --activate

# Copy package files
COPY package.json ./

# Install dependencies
RUN pnpm install

# Copy source files
COPY . .

# Build arguments for Vite environment variables
ARG VITE_API_URL=http://localhost:16380
ARG VITE_WS_URL=ws://localhost:16380
ARG VITE_ASR_ENDPOINT
ARG VITE_TTS_ENDPOINT

# Make them available to Vite at build time
ENV VITE_API_URL=$VITE_API_URL
ENV VITE_WS_URL=$VITE_WS_URL
ENV VITE_ASR_ENDPOINT=$VITE_ASR_ENDPOINT
ENV VITE_TTS_ENDPOINT=$VITE_TTS_ENDPOINT

# Build the application
RUN pnpm build

# Stage 2: Production
FROM node:20-alpine AS production

WORKDIR /app

# Install corepack for pnpm
RUN corepack enable && corepack prepare pnpm@latest --activate

# Copy package files for production dependencies
COPY package.json ./

# Install production dependencies only
RUN pnpm install --production

# Copy built files from builder stage
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/server ./server

# Set environment
ENV NODE_ENV=production
ENV PORT=3000

# Expose port
EXPOSE 3000

# Start the server
CMD ["node", "dist/index.js"]
