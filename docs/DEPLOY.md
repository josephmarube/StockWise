# Deploying StockWise (Azure Database for MySQL + Render)

The production setup is one Docker container that serves both the API and the React app from a single HTTPS address. The database is Azure Database for MySQL Flexible Server (free for 12 months with Azure for Students).

```
Phone / laptop ──HTTPS──▶ Render (Docker: FastAPI + built React) ──TLS──▶ Azure MySQL
```

Time needed: about 30 minutes, most of it waiting for builds.

## 1. Create the database on Azure

1. In the Azure portal (Azure for Students), create **Azure Database for MySQL – Flexible Server**:
   - Resource group: `stockwise-rg`
   - Region: one your subscription allows (check **Policy → Allowed locations**). UAE North was used.
   - Workload type **For development or hobby projects**: compute **B1ms**, storage 20 GiB, MySQL **8.0**
   - Authentication: **MySQL authentication only**; admin username `stockwise`
2. **Networking:** public access, and add the firewall rule `0.0.0.0`–`255.255.255.255`. Render's free plan has no fixed outbound IP, so this is needed. The server still requires TLS and a password.
3. When the server shows **Ready**, open **Databases → Add** and create a database named `stockwise`.
4. **CA certificate:** Azure's server certificates chain to one of three roots. Download *DigiCert Global Root CA*, *DigiCert Global Root G2* and *Microsoft RSA Root CA 2017* (all in PEM format), and join them into one file, `backend/azure-ca.pem`. It is git-ignored (`*.pem`), so it won't be committed.

Your connection string has this form (keep `ssl-mode=REQUIRED`):

```
mysql://stockwise:<PASSWORD>@<server-name>.mysql.database.azure.com/stockwise?ssl-mode=REQUIRED
```

If the password contains characters such as `@`, `#` or `/`, URL-encode them (for example `@` becomes `%40`).

## 2. Load the demo data into Azure (from your laptop)

In `backend/`, with the venv active:

```bash
export DATABASE_URL='<your Azure connection string>'
export DATABASE_SSL_CA=azure-ca.pem
python -m scripts.seed
```

Paste your own connection string, and keep the single quotes. This creates the tables over an encrypted connection and loads two demo businesses (Mama Njeri Duka and Kilimani Hardware).

To start empty instead, skip this step. The tables are created automatically on first start, and anyone can create a business at `/signup`.

**Demo passwords:** without `SEED_PASSWORD`, the demo accounts use the passwords listed in the README, so assessors can log in. Anyone with those passwords can change the demo data, so run `python -m scripts.seed --reset` shortly before a demo or assessment to restore it. For a real (non-demo) deployment, set `export SEED_PASSWORD='<a strong password>'` before seeding, or skip seeding. Anyone can also create their own business at `/signup`.

## 3. Deploy the app on Render

1. Push the repo to GitHub.
2. Sign in at [render.com](https://render.com) with GitHub.
3. **New → Blueprint**, pick the `StockWise` repo. Render reads `render.yaml` and asks for two values:
   - `DATABASE_URL`: your Azure connection string, with the real password.
   - `DATABASE_CA_CERT`: open `azure-ca.pem` in a text editor and paste all of it (all three certificates), including every `-----BEGIN CERTIFICATE-----` and `-----END CERTIFICATE-----` line.

   `JWT_SECRET` is generated for you.
4. **Apply.** The first build takes 5–10 minutes. When it shows **Live**, open the `https://stockwise-….onrender.com` link.
5. On your phone, open the same link, go to **Record → Scan** and allow the camera.

Every `git push` to `main` redeploys automatically.

**Free plan behaviour:** the service sleeps after about 15 minutes without visits, and the next visit takes up to a minute to wake it. Open the site a minute before recording your demo or presenting.

## 4. Create a System Admin

System Admins (StockWise staff) can't sign up on the website. Create one from your laptop against the live database, in `backend/` with the venv active:

```bash
export DATABASE_URL='<your Azure connection string>'
export DATABASE_SSL_CA=azure-ca.pem
python -m scripts.create_system_admin --email you@example.com --name "Your Name"
```

It asks for the password twice. Then log in on the live site's normal login page; you land in the System Admin area. (If you seeded the live database, the demo System Admin `support@stockwise.co.ke` already exists.)

Upgrading an existing deployment needs no manual step: on the next deploy, migration 0004 runs automatically, turns every Admin into a Manager and adds the activity log table.

## 5. Check it

- `https://…onrender.com/api/health` should return `{"status":"ok"}`.
- Render's **Logs** tab should show `Database is up to date.` followed by `Application startup complete.`

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `Set JWT_SECRET to a random string…` in logs | The secret is missing or short. In Render → Environment, set `JWT_SECRET` (or let the blueprint generate it). |
| `CERTIFICATE_VERIFY_FAILED` | `DATABASE_CA_CERT` is missing part of the certificate. Paste the whole file again, including the BEGIN/END lines. |
| `Access denied for user 'stockwise'` | The password in `DATABASE_URL` is wrong or not URL-encoded. Reset it in Azure under the server's **Overview → Reset password**. |
| `Can't connect to MySQL server` | The server is stopped or still starting, or the firewall blocks you. In Azure, check it shows **Ready** and that **Networking** has the firewall rule from step 1. |
| Azure deployment fails with `InsufficientCapacityForPlacement` or a region policy error | The region has no capacity, or your subscription doesn't allow it. Pick another region from **Policy → Allowed locations** (UAE North worked). |
| Warning: `server certificate is not verified` | `DATABASE_CA_CERT` isn't set. The connection is still encrypted, but set the CA to verify the server. |
| Site takes ~1 minute to load | The free instance was asleep. Normal on the free plan. |

## Running the production image locally (optional)

With Docker Desktop installed:

```bash
cp .env.example .env      # fill in MYSQL_PASSWORD, MYSQL_ROOT_PASSWORD, JWT_SECRET
docker compose up --build
docker compose exec app python -m scripts.seed
```

Open http://localhost:8080. This runs the same image as Render, with its own MySQL container instead of Azure.

## How the image works

- **Two build stages.** Stage 1 builds the React app with Node 20. Stage 2 is Python 3.12 with the API, plus the built files in `/app/static`.
- **Startup.** On start the container runs `python -m app.migrate` once (Alembic), then starts Uvicorn with `WEB_CONCURRENCY` workers. Migrating first means two workers never migrate at the same time.
- **Routing.** FastAPI serves `/api/*`, the files under `/assets/` (cached for a year, since their names contain a content hash), and `index.html` for every other path, so links like `/products/3` work.
- **Connection string.** `DATABASE_URL` accepts the `mysql://…?ssl-mode=REQUIRED` form used by Azure and other MySQL hosts directly. The app converts it for PyMySQL and turns on TLS.
- **Certificate checking.** When a CA is given, the server certificate and hostname are both verified.
