# The build output is static files, so build once on the host's native
# platform (fast, no emulation) and reuse it for every target platform.
FROM --platform=$BUILDPLATFORM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
# Shown in the app's sidebar so you can tell which build is deployed.
ARG OPENFAMHUB_BUILD=dev
ENV VITE_APP_BUILD=$OPENFAMHUB_BUILD
RUN npm run build

FROM nginx:alpine
# Pick up Alpine security fixes released since the base image was built.
RUN apk upgrade --no-cache
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 3000
