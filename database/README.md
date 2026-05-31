# Base de datos

## Instalación desde cero

```bash
mysql -u root -p < BD_Amicana.sql
```

`BD_Amicana.sql` es el schema canónico consolidado: crea la BD `gestion_facturas_amicana`, las 13 tablas y los seeds (niveles CEFR, cursos default, preferencias del sistema). **Es lo único que necesitás correr para una instalación nueva.**

## Upgrade de instalación vieja

Si ya tenés datos viejos en la BD, NO uses `BD_Amicana.sql` — aplicá las migraciones incrementales de `migrations/` en orden numérico. Ver [`migrations/README.md`](migrations/README.md).
