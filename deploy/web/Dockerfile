FROM node:24-alpine@sha256:ebfe2f90462722a7a4de65e91990e97fe0d401c70e0e762c5b53302f905ec1c1 AS build
WORKDIR /build
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM nginxinc/nginx-unprivileged:stable-alpine@sha256:ed04ec1ff34502c339ee5c3ae3f855442398edc1d05591e2b98981dcbbd20b1e
USER root
RUN apk add --no-cache python3
COPY --from=build /build/dist /usr/share/nginx/html
COPY deploy/web/render.py /opt/unum-web/render.py
USER 101
EXPOSE 8080
ENTRYPOINT ["/bin/sh", "-c", "python3 /opt/unum-web/render.py /etc/unum-web/runtime.json && exec nginx -c /tmp/unum-web/nginx.conf -g 'daemon off;'"]
