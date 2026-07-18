# _template

Copy this directory to create a service — full walkthrough in
[docs/adding-a-service.md](../../docs/adding-a-service.md). The underscore
prefix keeps this directory out of platform discovery; your copy (no
underscore) deploys automatically.

The most likely mistake: forgetting to make the service name in
`compose.yaml` match the new directory name. `make smoke` exists to prove
the pathway stays healthy.

House rules: [CLAUDE.md](../../CLAUDE.md).
