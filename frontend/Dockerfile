FROM node:24-bookworm-slim AS build

WORKDIR /app

COPY package.json package-lock.json .npmrc ./
RUN npm ci

COPY . ./
# Public origin and Metrika counter are inlined into the bundle at build time;
# the production compose override passes them as build args.
ARG PUBLIC_SITE_URL=https://memiro.ru
ARG PUBLIC_METRIKA_ID=
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
