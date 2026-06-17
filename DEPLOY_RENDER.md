# Deploy BookNest to Render

This setup is intended for a small personal BookNest deployment that should stay responsive for a private library of hundreds of books.

## Recommended Render setup

Use the paid Render resources in `render.yaml`:

- Web service: `starter`
- PostgreSQL: `basic-256mb`

Render's free web services spin down after idle time, which makes the first request slow. The `starter` web service avoids that cold-start delay. The PostgreSQL database keeps book, shelf, and note data outside the web service filesystem.

## Deploy steps

1. Push this repository to GitHub.
2. In Render, choose **New → Blueprint**.
3. Connect the repository and select the branch that contains `render.yaml`.
4. Render will create:
   - `booknest` web service
   - `booknest-db` PostgreSQL database
5. Wait for the first deploy to finish.
6. Open the Render service URL and register/login.

## Important notes

- `render.yaml` runs migrations on service start.
- Static files are collected during build by `build.sh`.
- Uploaded cover files stored on the local filesystem are not permanent unless a persistent disk/object storage is added. For the safest first deployment, prefer cover URLs or add persistent media storage later.
- Render sets `RENDER_EXTERNAL_HOSTNAME`; the Django settings use it for `ALLOWED_HOSTS` automatically.