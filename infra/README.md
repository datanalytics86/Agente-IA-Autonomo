# Infra

Demo local. No hay envíos reales: el compose fija `APP_MODE=demo`, `DRY_RUN=true` y `OUTREACH_ENABLED=false` salvo que el entorno los tape. Sin esas credenciales no sale correo, WhatsApp ni un cobro.

## Levantar

Hace falta Docker. Desde la raíz del repo:

```powershell
docker compose -f infra/docker-compose.yml up --build
```

```bash
docker compose -f infra/docker-compose.yml up --build
```

- Sitio público (marcador hasta que exista `apps/site`): http://localhost/
- `/api`, `/webhooks`, `/demo` y `/u` se proxean a `api` (puerto interno 8000).
- Dashboard estático: http://localhost/admin tras `npm run build` en `apps/web`. El build actual pide `/assets` en la raíz; el `base` `/admin` lo cierra A6.
- Postgres 16 solo en `127.0.0.1:5432`. Usuario, clave y base de demo: `agencia`. No sirve fuera de esta máquina.
- `/demo/*` lleva `X-Robots-Tag: noindex, nofollow`. El resto del sitio no.

`api` arranca con `python main.py --mode api` y `worker` con `--mode worker`. Si el paquete todavía no está, el proceso sale con código 2. No es un deploy.

El contexto de la imagen es la raíz del repo. `.dockerignore` excluye `.env`. No metas secretos en el compose.

## Backup

`infra/scripts/backup.sh` y `infra/scripts/backup.ps1` hacen `pg_dump` y dejan 14 archivos. La restauración se prueba en F7. No los corras contra una base real antes de eso. Los volcados quedan en `./backups` (o `BACKUP_DIR`); no se commitean.
