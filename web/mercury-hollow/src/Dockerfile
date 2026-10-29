FROM node:22-alpine AS builder

# Install build dependencies for native modules
RUN apk add --no-cache python3 make g++

WORKDIR /app

# Copy package files
COPY package*.json ./
COPY pnpm-lock.yaml ./

# Install pnpm
RUN npm install -g pnpm@9.15.9

# Install ALL dependencies (including dev dependencies)
RUN pnpm install --frozen-lockfile --unsafe-perm

# Copy source code
COPY . .

# Build the application
RUN pnpm run build

# Production stage
FROM node:22-alpine AS production

WORKDIR /app

# Copy package files
COPY package*.json ./
COPY pnpm-lock.yaml ./

# Install pnpm
RUN npm install -g pnpm@9.15.9

# Install ONLY production dependencies
RUN pnpm install --prod --frozen-lockfile --unsafe-perm

# Copy built application from builder stage
COPY --from=builder /app/dist ./dist

# Copy views directory
COPY --from=builder /app/src/views ./views

# Copy public challenge artifacts and placeholder images
COPY --from=builder /app/public ./public

# Expose port
EXPOSE 3000

# Start the application
CMD ["node", "dist/main.js"]
