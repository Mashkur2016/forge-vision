FROM node:22-alpine

WORKDIR /app/frontend

# Install dependencies as a separate cached layer
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

# Copy remaining source (node_modules already installed above)
COPY frontend/ ./

EXPOSE 5173

# --host overrides server.host: '127.0.0.1' in vite.config.ts
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
