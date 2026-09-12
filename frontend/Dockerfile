# --- build stage ---
FROM node:20-alpine AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Baked into the static bundle at build time (Vite inlines import.meta.env.*).
# Defaults to the mock API so the image runs standalone; override at build
# time once the real backend is wired up (see docker-compose.yml).
ARG VITE_USE_MOCK=true
ARG VITE_API_BASE_URL=/api
ENV VITE_USE_MOCK=$VITE_USE_MOCK
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

RUN npm run build

# --- serve stage ---
FROM nginx:1.27-alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf.template /etc/nginx/templates/default.conf.template

# Where nginx proxies /api/* to. Matches the "backend" service name used in
# docker-compose.yml; override with -e BACKEND_ORIGIN=... for other setups.
ENV BACKEND_ORIGIN=http://backend:8000

EXPOSE 80
