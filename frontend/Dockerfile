FROM node:20-alpine AS build
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
# Vite inlines env vars at build time, not container start — so the
# backend's URL has to arrive as a build ARG, not a runtime env var.
# Empty/unset falls back to api.js's own "/api" default (same-origin,
# nginx-proxied), preserving the existing docker-compose behavior exactly.
ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
