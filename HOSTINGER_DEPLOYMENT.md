# Upmart FastAPI deployment on Hostinger KVM 1

This repository deploys only the FastAPI API and PostgreSQL. The customer and
admin React applications remain on Vercel.

## Production layout

```text
Vercel sites -> https://api.upmart.co.in -> Nginx -> FastAPI container -> PostgreSQL container
```

Only SSH (22), HTTP (80), and HTTPS (443) are public. FastAPI binds to
`127.0.0.1:8000`; PostgreSQL has no published port. The `postgres_data` and
`uploads_data` Docker volumes persist the database, product images, logos, and
site settings across container replacements.

The application is installed under `/srv/apps/upmart-api` and owned by the
non-root `deploy` account. Future applications should use their own directory,
Compose project name, loopback port, and Nginx site—for example
`/srv/apps/another-api` on `127.0.0.1:8001`.

## 1. Create and secure the VPS

Install Ubuntu 24.04 LTS in hPanel, then connect as root:

```bash
ssh root@YOUR_HOSTINGER_IP
apt update && apt upgrade -y
apt install -y ca-certificates curl git nginx certbot python3-certbot-nginx ufw fail2ban
adduser deploy
usermod -aG sudo deploy
```

Copy your SSH public key to the new `deploy` account and confirm a new SSH
session works before changing SSH authentication settings.

Configure the firewall:

```bash
ufw allow OpenSSH
ufw allow "Nginx Full"
ufw enable
ufw status
```

Do not open ports 5432 or 8000.

Add 2 GB swap for Docker builds on the 4 GB VPS:

```bash
fallocate -l 2G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
```

Install Docker Engine and the Compose plugin from Docker's Ubuntu repository:

```bash
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
. /etc/os-release
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $VERSION_CODENAME stable" > /etc/apt/sources.list.d/docker.list
apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable --now docker
```

Verify both commands, then grant the deployment user access:

```bash
docker --version
docker compose version
usermod -aG docker deploy
```

Log out and reconnect as `deploy`.

## 2. Create the reusable application layout

```bash
sudo mkdir -p /srv/apps /srv/backups
sudo chown deploy:deploy /srv/apps /srv/backups
cd /srv/apps
git clone YOUR_FASTAPI_GITHUB_REPOSITORY_URL upmart-api
cd upmart-api
```

From this point onward, run Git and Docker commands as `deploy`, not root. Use
`sudo` only for shared operating-system configuration such as Nginx and UFW.

The repository must contain `Dockerfile`, `compose.yml`, `main.py`, and
`requirements.txt` at this level.

## 3. Create production secrets

Generate values containing only hexadecimal characters so they are safe inside
the PostgreSQL URL:

```bash
openssl rand -hex 32
openssl rand -hex 64
```

Create the production file from the template:

```bash
cp .env.production.example .env
nano .env
chmod 600 .env
```

Replace both placeholder secrets. Never commit `.env`.

When importing the repository through Hostinger Docker Manager, enter these
same variables in the project's environment-variable editor. Docker Manager
does not import the ignored local `.env` file from Git. Compose will now stop
with a clear message if either required secret is absent.

Keep these values unique per application:

```env
COMPOSE_PROJECT_NAME=upmart_api
API_BIND_PORT=8000
```

A future application could use `COMPOSE_PROJECT_NAME=another_api` and
`API_BIND_PORT=8001`. This prevents container, network, volume, and port
collisions.

## 4. Build and start

```bash
docker compose config --quiet
docker compose up -d --build
docker compose ps
docker compose logs --tail=100 api
curl http://127.0.0.1:8000/health
```

Both services must show `healthy` before continuing.

## 5. Create the fresh schema and administrator

The application intentionally does not mutate the database schema on startup.
For the first fresh deployment, create all current tables once:

```bash
docker compose exec api python -c "from database import Base, engine; import models; Base.metadata.create_all(bind=engine); print('Schema created')"
docker compose exec api python create_admin_safe.py
```

Do not run `seed.py` in production; it creates known sample credentials and
sample commerce data.

## 6. Test before changing DNS

Copy the supplied Nginx configuration:

```bash
sudo cp deploy/nginx/upmart-api.conf /etc/nginx/sites-available/upmart-api
sudo ln -s /etc/nginx/sites-available/upmart-api /etc/nginx/sites-enabled/upmart-api
sudo nginx -t
sudo systemctl reload nginx
```

From your own computer, test the new IP without switching production DNS:

```bash
curl --resolve api.upmart.co.in:80:YOUR_HOSTINGER_IP http://api.upmart.co.in/health
```

## 7. Switch DNS and enable HTTPS

Set the DNS record where `upmart.co.in` is managed:

```text
Type: A
Name: api
Value: YOUR_HOSTINGER_IP
TTL: 300
```

After `api.upmart.co.in` resolves to Hostinger:

```bash
sudo certbot --nginx -d api.upmart.co.in
curl https://api.upmart.co.in/health
sudo certbot renew --dry-run
```

Both Vercel projects must use:

```env
VITE_API_URL=https://api.upmart.co.in
```

If that exact value is already configured, the frontends need no code change.
Redeploy them only if the Vercel environment value changes.

## 8. Production acceptance checks

- Admin login works and invalid login returns 401.
- Categories, products, variants, customers, coupons, and orders work.
- JPEG, PNG, WebP, and GIF uploads work; oversized/invalid files are rejected.
- Product images and logo remain after `docker compose restart`.
- Settings remain after `docker compose up -d --build`.
- Browser developer tools show no CORS or mixed-content errors.
- Ports 5432 and 8000 are not accessible from the internet.
- `docker compose ps` shows both services healthy after a VPS reboot.

Keep AWS running until these checks pass.

## 9. Routine deployment

```bash
cd /srv/apps/upmart-api
git pull --ff-only
docker compose up -d --build
docker compose ps
docker compose logs --tail=100 api
docker image prune -f
```

Never run `docker compose down -v`; `-v` deletes the persistent volumes.

## 10. Backup and restore

Create a backup directory:

```bash
mkdir -p /srv/backups/upmart-api
```

Back up PostgreSQL:

```bash
cd /srv/apps/upmart-api
docker compose exec -T db pg_dump -U upmart_user -d upmart | gzip > /srv/backups/upmart-api/upmart-$(date +%F-%H%M).sql.gz
```

Back up uploads and settings:

```bash
docker compose exec -T api tar -czf - -C /app/uploads . > /srv/backups/upmart-api/uploads-$(date +%F-%H%M).tar.gz
```

Copy backups to another machine or storage provider. Backups kept only on the
same VPS do not protect against disk or account loss.

Restore PostgreSQL into an empty `upmart` database:

```bash
gunzip -c BACKUP.sql.gz | docker compose exec -T db psql -U upmart_user -d upmart
```

## 11. Troubleshooting

```bash
docker compose ps
docker compose logs -f api
docker compose logs -f db
sudo nginx -t
sudo journalctl -u nginx --since "30 minutes ago"
df -h
free -h
docker system df
```
