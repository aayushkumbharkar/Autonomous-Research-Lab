# Stage 1: Build static assets
FROM node:22-alpine AS build

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

# We set VITE_API_URL to /api so that Nginx reverse proxies it to the backend container
ENV VITE_API_URL=/api
RUN npm run build

# Stage 2: Serve static files with Nginx
FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
