# Deploying StockWise (Aiven MySQL + Render)

The production setup is one Docker container that serves both the API and the React app from a single HTTPS address. The database is a free MySQL service on Aiven.

```
Phone / laptop ──HTTPS──▶ Render (Docker: FastAPI + built React) ──TLS──▶ Aiven MySQL
```

Time needed: about 30 minutes, most of it waiting for builds.

## 1. Create the database on Aiven

1. Sign up at [aiven.io](https://aiven.io) and create a project.
2. **Create service → MySQL → Free plan.** Pick a region close to where the app will run. The blueprint uses Render's **Frankfurt** region, so choose a European region if one is offered. Name it `stockwise-db`.
3. Wait until the service shows **Running** (a few minutes).
4. On the service's **Overview** page, note two things:
   - **Service URI**, for example `mysql://avnadmin:…@stockwise-db-yourproject.aivencloud.com:12345/defaultdb?ssl-mode=REQUIRED`
   - **CA certificate**: click *Download* and save it as `backend/ca.pem`. It is git-ignored, so it won't be committed.

Check the free plan's limits in the Aiven console (storage, and whether idle services are powered off). They are generous for a coursework demo.

## 2. Load the demo data into Aiven (from your laptop)

In `backend/`, with the venv active:

```bash
export DATABASE_URL='mysql://avnadmin:…@….aivencloud.com:12345/defaultdb?ssl-mode=REQUIRED'
export DATABASE_SSL_CA=ca.pem
python -m scripts.seed
```

Paste your own Service URI, and keep the single quotes. This creates the tables over an encrypted connection and loads two demo businesses (Mama Njeri Duka and Kilimani Hardware).

To start empty instead, skip this step. The tables are created automatically on first start, and anyone can create a business at `/signup`.

**Security:** the demo passwords are public in the README. After deploying, log in as each demo admin and change the passwords on the **Users** page, then give your assessors the new details in your submission. Assessors can also create their own business at `/signup`.

## 3. Deploy the app on Render

1. Push the repo to GitHub.
2. Sign in at [render.com](https://render.com) with GitHub.
3. **New → Blueprint**, pick the `StockWise` repo. Render reads `render.yaml` and asks for two values:
   - `DATABASE_URL`: the Aiven **Service URI**, exactly as shown.
   - `DATABASE_CA_CERT`: open `ca.pem` in a text editor and paste all of it, including the `-----BEGIN CERTIFICATE-----` and `-----END CERTIFICATE-----` lines.

   `JWT_SECRET` is generated for you.
4. **Apply.** The first build takes 5–10 minutes. When it shows **Live**, open the `https://stockwise-….onrender.com` link.
5. On your phone, open the same link, go to **Record → Scan** and allow the camera.

Every `git push` to `main` redeploys automatically.

**Free plan behaviour:** the service sleeps after about 15 minutes without visits, and the next visit takes up to a minute to wake it. Open the site a minute before recording your demo or presenting.

## 4. Check it

- `https://…onrender.com/api/health` should return `{"status":"ok"}`.
- Render's **Logs** tab should show `Database is up to date.` followed by `Application startup complete.`

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `Set JWT_SECRET to a random string…` in logs | The secret is missing or short. In Render → Environment, set `JWT_SECRET` (or let the blueprint generate it). |
| `CERTIFICATE_VERIFY_FAILED` | `DATABASE_CA_CERT` is missing part of the certificate. Paste the whole file again, including the BEGIN/END lines. |
| `Access denied for user 'avnadmin'` | The password in `DATABASE_URL` is wrong. Copy the Service URI again from Aiven. |
| `Can't connect to MySQL server` | The Aiven service is powered off or still starting. Check it shows **Running**. |
| Warning: `server certificate is not verified` | `DATABASE_CA_CERT` isn't set. The connection is still encrypted, but set the CA to verify the server. |
| Site takes ~1 minute to load | The free instance was asleep. Normal on the free plan. |

## Running the production image locally (optional)

With Docker Desktop installed:

```bash
docker compose up --build
docker compose exec app python -m scripts.seed
```

Open http://localhost:8080. This runs the same image as Render, with its own MySQL container instead of Aiven.

## How the image works

- **Two build stages.** Stage 1 builds the React app with Node 20. Stage 2 is Python 3.12 with the API, plus the built files in `/app/static`.
- **Startup.** On start the container runs `python -m app.migrate` once (Alembic), then starts Uvicorn with `WEB_CONCURRENCY` workers. Migrating first means two workers never migrate at the same time.
- **Routing.** FastAPI serves `/api/*`, the files under `/assets/` (cached for a year, since their names contain a content hash), and `index.html` for every other path, so links like `/products/3` work.
- **Connection string.** `DATABASE_URL` accepts Aiven's `mysql://…?ssl-mode=REQUIRED` form directly. The app converts it for PyMySQL and turns on TLS.
- **Certificate checking.** When a CA is given, the server certificate and hostname are both verified.
