FROM node:24-bookworm-slim AS build

WORKDIR /app

COPY package.json package-lock.json .npmrc ./
RUN npm ci

COPY . ./
# The public origin is inlined into the bundle at build time; the Metrika
# counter is not — it is read from the environment on every render (ADR-0006).
ARG PUBLIC_SITE_URL=https://memiro.ru
RUN npm run build && npm prune --omit=dev

FROM node:24-bookworm-slim

WORKDIR /app
ENV HOST=0.0.0.0
ENV NODE_ENV=production

COPY package.json server.mjs ./
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/dist ./dist

USER node
EXPOSE 4321
# node is PID 1 on purpose: npm would swallow SIGTERM and the container would die by timeout.
CMD ["node", "./server.mjs"]
