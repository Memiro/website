FROM node:24-bookworm-slim AS build

WORKDIR /app

COPY package.json package-lock.json .npmrc ./
RUN npm ci

COPY . ./
RUN npm run build && npm prune --omit=dev

FROM node:24-bookworm-slim

WORKDIR /app
ENV HOST=0.0.0.0
ENV NODE_ENV=production

COPY package.json ./
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/dist ./dist

EXPOSE 4321
CMD ["npm", "run", "start"]
