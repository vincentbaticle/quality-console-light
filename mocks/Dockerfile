# Prism on the machine's own platform: the stoplight/prism image is built for
# amd64 only, and emulating five of them starves the rest of the stack.
FROM node:22.20.0-alpine3.22
RUN npm install --global --omit=dev @stoplight/prism-cli@5.15.10 && npm cache clean --force
WORKDIR /mocks
COPY router.mjs /mocks/router.mjs
EXPOSE 4010
ENTRYPOINT ["node", "/mocks/router.mjs"]
