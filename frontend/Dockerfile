FROM node:22-alpine

WORKDIR /web

COPY package.json package-lock.json ./
COPY tsconfig.json .
COPY vite.config.ts .
COPY index.html .
COPY src ./src
COPY scripts ./scripts

RUN npm ci --no-audit --no-fund \
    && npm run build \
    && npm run test:build

EXPOSE 5173

CMD ["npm", "run", "dev"]
