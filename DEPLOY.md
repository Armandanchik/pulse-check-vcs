# Deploying Pulse Check

The app runs as three Docker containers: **web** (Django), **db** (PostgreSQL) and **caddy** (HTTPS). The same setup works on a cheap VPS now and on a VCS server later.

## What you need

- A small Linux server (Ubuntu 24.04, 2 GB RAM is plenty), e.g. Hetzner CX22 or DigitalOcean (~€4–6/month)
- A domain or subdomain pointing at the server's IP (an **A record**), e.g. `pulse.yourdomain.lt`

## First install

On the server (logged in with `ssh root@SERVER_IP`):

```bash
# 1. Install Docker
curl -fsSL https://get.docker.com | sh

# 2. Get the code (the repo is private: log in with the GitHub CLI or use a deploy key)
git clone https://github.com/Armandanchik/pulse-check-vcs.git
cd pulse-check-vcs

# 3. Configure
cp .env.example .env
nano .env        # fill in DOMAIN, DJANGO_SECRET_KEY, DJANGO_ALLOWED_HOSTS, PUBLIC_BASE_URL, POSTGRES_PASSWORD

# 4. Start
docker compose up -d --build

# 5. Create your admin login and load the AI Engineering program
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py seed_ai_engineering
```

Open `https://your-domain/admin/`, create the group, and click **Sugeneruoti sesijas**. The group page then shows the student link and QR code.

## Updating to a new version

```bash
cd pulse-check-vcs
git pull
docker compose up -d --build
```

Database migrations run automatically on start.

## Backups

Daily database dump, kept for 30 days:

```bash
mkdir -p /root/backups
crontab -e
# add this line:
0 3 * * * cd /root/pulse-check-vcs && docker compose exec -T db pg_dump -U pulse pulse | gzip > /root/backups/pulse-$(date +\%F).sql.gz && find /root/backups -mtime +30 -delete
```

## Moving to a VCS server

Copy the repo and `.env`, restore the latest backup into the new database, and point the domain at the new server:

```bash
docker compose up -d db
gunzip -c pulse-YYYY-MM-DD.sql.gz | docker compose exec -T db psql -U pulse pulse
docker compose up -d --build
```
