# Construction (multi-arch, compatible Apple Silicon)
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build

# Service statique + reverse proxy vers l'API
FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY securite.conf /etc/nginx/securite.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
