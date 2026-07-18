FROM golang:1.26-alpine AS build
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -o /out/worker ./cmd/worker \
 && CGO_ENABLED=0 go build -o /out/eventgen ./cmd/eventgen

# Pure-Go binaries, no TLS clients: scratch is enough. eventgen ships in
# the image so demos can `docker exec` it against the shared volume.
FROM scratch
COPY --from=build /out/worker /worker
COPY --from=build /out/eventgen /eventgen
ENTRYPOINT ["/worker"]
