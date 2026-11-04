# Build from repository root: docker build -f implementation/marketing/Dockerfile .
# Build Stage
FROM node:22-alpine AS builder

WORKDIR /repo/implementation/marketing

# Copy package manifests first for optimal layer caching
COPY implementation/marketing/package.json implementation/marketing/package-lock.json implementation/marketing/.npmrc ./

# Install dependencies
RUN npm ci

# Copy configuration files and source code
COPY implementation/marketing/index.html implementation/marketing/vite.config.ts implementation/marketing/tsconfig*.json ./
COPY implementation/marketing/public/ ./public/
COPY implementation/marketing/src/ ./src/
# Pilot privacy imports this reviewed source notice outside the marketing directory.
COPY docs/release/pilot-registration/notice.json /repo/docs/release/pilot-registration/notice.json

# Build production bundle
RUN npm run build

# Production Stage (Nginx)
FROM nginx:alpine AS production

# Remove default nginx static assets
RUN rm -rf /usr/share/nginx/html/*

# Copy custom Nginx configuration
COPY implementation/marketing/nginx.conf /etc/nginx/conf.d/default.conf
COPY implementation/marketing/security-headers.conf /etc/nginx/security-headers.conf

# Copy build artifacts from builder stage
COPY --from=builder /repo/implementation/marketing/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
