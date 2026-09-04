# Same shape as ../../default/frontend/Dockerfile — see that file's own header comment.
FROM node:22-alpine
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1

COPY package.json package-lock.json /app/
COPY frontend/ /app/frontend/
COPY playground/subclassed/frontend/ /app/playground/subclassed/frontend/
COPY playground/default/frontend/package.json /app/playground/default/frontend/package.json
RUN npm install

WORKDIR /app/playground/subclassed/frontend

EXPOSE 3000
CMD ["npm", "run", "dev", "--", "--hostname", "0.0.0.0", "--port", "3000"]
