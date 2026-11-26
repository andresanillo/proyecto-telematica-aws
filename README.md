# Proyecto Final Telemática · App web con balanceador, autoescalado y RDS (AWS)

App Flask para crear, modificar, eliminar y listar usuarios (Nombre, Apellido, Cédula, Teléfono, Carrera),
con una seña en `index.html` que muestra qué instancia EC2 respondió (ID, IP privada, zona y color).

## Estructura
| Archivo | Para qué |
|---|---|
| `app.py` | La app: CRUD, total, seña de la instancia y ruta `/stress` |
| `carreras.py` | Lista de carreras del menú desplegable |
| `templates/index.html` | La página (Bootstrap) con la seña |
| `requirements.txt` | Librerías de Python |
| `schema.sql` | La tabla `usuarios` (la app la crea sola; es de referencia) |
| `scripts/user_data.sh` | Script del Launch Template: instala y arranca la app en cada EC2 |
| `scripts/estres.sh` | Estrés de CPU por SSH (respaldo) |
| `.env.example` | Plantilla de variables para probar en local |

## Probar en local (Ubuntu)
```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # ajusta la contraseña de tu MySQL local
python app.py               # abre http://localhost:5000
```

## En AWS
La app corre con gunicorn en el puerto 80, instalada por `scripts/user_data.sh`.
Las credenciales de la base de datos van en el user data (archivo `/etc/app.env` en cada servidor), nunca en el repo.
