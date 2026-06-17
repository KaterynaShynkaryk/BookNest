# Deploy BookNest to Render

This setup is intended for a small personal BookNest deployment that should stay responsive for a private library of hundreds of books.

## Free Render setup

This project is configured for Render's free resources in `render.yaml`:

- Web service: `free`
- PostgreSQL: `free`

This should let you try the deployment without adding a payment card. Free web services can spin down after idle time, so the first request after a pause can be slow. Free Render PostgreSQL databases expire after a limited time, so this is best for testing before choosing a permanent storage option.

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
- Uploaded cover files stored on the local filesystem are not permanent on Render free services. For the safest free deployment, prefer cover URLs instead of uploaded cover files.
- Free Render services are useful for testing, but they are not ideal for permanent personal data. Export or back up your data before the free database expires.
- Render sets `RENDER_EXTERNAL_HOSTNAME`; the Django settings use it for `ALLOWED_HOSTS` automatically.