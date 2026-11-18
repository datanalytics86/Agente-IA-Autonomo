# rclone hacia R2

El script no crea la cuenta ni el bucket. El operador configura rclone en el host y deja el remoto en `RCLONE_DEST` (por ejemplo `r2:agencia-backups-prod`).

Un remoto S3 compatible con Cloudflare R2, sin secretos en el repo:

```bash
rclone config create r2 s3 \
  provider Cloudflare \
  access_key_id "$R2_ACCESS_KEY_ID" \
  secret_access_key "$R2_SECRET_ACCESS_KEY" \
  endpoint "$R2_ENDPOINT" \
  acl private
```

El archivo queda en `/root/.config/rclone/rclone.conf` (root 600), porque `agencia-backup` corre como root. La retención de objetos está en `infra/r2-lifecycle.json` y se aplica en el bucket, no desde este script.
