# Deployment (Docker, Google Cloud Run)

The app runs in a Docker container (`Dockerfile`, dependencies installed with uv from `uv.lock`, served by gunicorn
`app:server`). Data files and images are part of the image: after changing them, commit and merge into `main` to
redeploy. The app stores nothing on the server (the browser session keeps the user's inputs), so no bucket or
secret is needed.

Hosting: Google Cloud Run (Nordic region), redeployed automatically by a Cloud Build trigger on every push to `main`.
Project identifiers and service-account names are kept in the maintainer's private notes, not in this repository.

## Settings (environment variables)

| Variable | Default | Purpose |
|---|---|---|
| `PORT` | `8080` | Set by Cloud Run |

## Security principles

- Dedicated service accounts, never the Compute Engine default account:
  - runtime account: no project roles and no resource grants (the app needs no Google Cloud resources);
  - build account: Cloud Run Admin, Artifact Registry Writer, Logs Writer, Service Account User on the runtime account.
- No secrets in the repository.

## Test the container locally (optional, needs Docker)

```bash
docker build -t edison-sri-tool .
docker run --rm -p 8080:8080 edison-sri-tool      # open http://localhost:8080
```

## Continuous deployment (Console)

Cloud Run → Deploy container → Continuously deploy from a repository → GitHub repo, branch `^main$`, Dockerfile;
public access, request-based billing, 0–3 instances, port 8080, 512 MiB, second-generation environment, runtime
service account. Then edit the generated Cloud Build trigger: build service account, and `logging: CLOUD_LOGGING_ONLY`
under `options:` in the inline YAML.
