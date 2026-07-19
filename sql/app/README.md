# SQL Server — BD operativa de la app

Base **PfiPrevencion** en `localhost` (instancia default).  
No es el core ART (`ART_CORE`); solo rankings importados, agenda, visitas y usuarios.

## Requisitos

- SQL Server 2025 Developer (o Express) en localhost
- Autenticación Windows (`-E`) o SQL auth en connection string
- `sqlcmd` en el PATH

## Crear / actualizar

```powershell
sqlcmd -S localhost -E -i sql/app/00_create_database.sql
sqlcmd -S localhost -E -i sql/app/01_schema.sql
```

## Connection string (API)

```
Server=localhost;Database=PfiPrevencion;Trusted_Connection=True;TrustServerCertificate=True;Encrypt=True
```

## Importar ranking

```powershell
$env:PYTHONPATH="src"
.\.venv\Scripts\python.exe scripts\import_ranking_to_app.py
```

## Usuario demo

- Email: `admin@pfi.local`
- Password: `Admin123!` (seteado por el seeder de la API al arrancar)
