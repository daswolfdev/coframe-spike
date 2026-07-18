FROM golang:1.26-alpine AS build
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -o /out/worker ./cmd/worker

# Pure-Go static binary, no TLS clients: scratch is enough.
FROM scratch
COPY --from=build /out/worker /worker
ENTRYPOINT ["/worker"]
