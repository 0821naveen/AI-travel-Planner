FROM node:20.11.1-bullseye

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm install --no-audit --no-fund

COPY public ./public
COPY src ./src
COPY tsconfig.json ./

EXPOSE 3000

CMD ["npm", "start"]
