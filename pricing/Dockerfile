FROM node:20-alpine

WORKDIR /app

# Only copy package files first for layer caching
COPY server/package*.json ./server/
RUN cd server && npm install --omit=dev

# Copy server and frontend
COPY server/ ./server/
COPY app/    ./app/
COPY data/   ./data/

EXPOSE 8742

CMD ["node", "server/index.js"]
