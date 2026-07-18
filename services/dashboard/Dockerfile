# Minor-pinned: mutable tags make next month's rebuild a different image.
FROM nginx:1.31-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY index.html app.js fixture.json /usr/share/nginx/html/
