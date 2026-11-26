"""
Proyecto Final Telemática - App web de usuarios (Opción 1)
Flask + MySQL (RDS) detrás de un balanceador de carga con autoescalado.

Rutas:
  GET  /                  -> página principal (seña de la instancia + formulario + lista + total)
  POST /crear             -> crea un usuario
  POST /actualizar/<id>   -> modifica un usuario
  POST /eliminar/<id>     -> elimina un usuario
  GET  /stress            -> pone la CPU de ESTA instancia al 100% por N segundos (para el autoescalado)
"""
import hashlib
import os
import subprocess
import sys
import urllib.request

import pymysql
from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, url_for

from carreras import CARRERAS

load_dotenv()  # en local lee el archivo .env; en AWS las variables vienen de /etc/app.env

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "admin")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "telematica")

app = Flask(__name__)
# Debe ser IGUAL en todas las instancias: si no, los mensajes (flash) se pierden
# cuando el balanceador manda la siguiente petición a otro servidor.
app.secret_key = os.getenv("SECRET_KEY", "cambia-esta-clave")


# ---------------------------------------------------------------------------
# Seña de la instancia (metadata de EC2 con IMDSv2)
# ---------------------------------------------------------------------------
METADATA_URL = "http://169.254.169.254/latest"


def _metadata(path, token):
    req = urllib.request.Request(f"{METADATA_URL}/meta-data/{path}",
                                 headers={"X-aws-ec2-metadata-token": token})
    with urllib.request.urlopen(req, timeout=1) as r:
        return r.read().decode()


def info_instancia():
    """Devuelve id, IP privada, zona y un color único para esta instancia."""
    try:
        req = urllib.request.Request(f"{METADATA_URL}/api/token", method="PUT",
                                     headers={"X-aws-ec2-metadata-token-ttl-seconds": "300"})
        with urllib.request.urlopen(req, timeout=1) as r:
            token = r.read().decode()
        info = {
            "id": _metadata("instance-id", token),
            "ip": _metadata("local-ipv4", token),
            "zona": _metadata("placement/availability-zone", token),
        }
    except Exception:
        # Corriendo en tu PC (no hay metadata de EC2)
        info = {"id": "local", "ip": "127.0.0.1", "zona": "mi-pc"}

    # Color distinto por instancia, sacado del ID (siempre el mismo para la misma VM)
    tono = int(hashlib.md5(info["id"].encode()).hexdigest(), 16) % 360
    info["color"] = f"hsl({tono}, 70%, 40%)"
    return info


INSTANCIA = info_instancia()  # se calcula una vez al arrancar


# ---------------------------------------------------------------------------
# Base de datos
# ---------------------------------------------------------------------------
def conectar(con_bd=True):
    return pymysql.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD,
        database=DB_NAME if con_bd else None,
        charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor,
        autocommit=True, connect_timeout=5,
    )


def iniciar_bd():
    """Crea la base de datos y la tabla si no existen (así no toca entrar a RDS a mano)."""
    with conectar(con_bd=False) as con, con.cursor() as cur:
        cur.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` CHARACTER SET utf8mb4")
    with conectar() as con, con.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id        INT AUTO_INCREMENT PRIMARY KEY,
                nombre    VARCHAR(60)  NOT NULL,
                apellido  VARCHAR(60)  NOT NULL,
                cedula    VARCHAR(20)  NOT NULL UNIQUE,
                telefono  VARCHAR(20)  NOT NULL,
                carrera   VARCHAR(80)  NOT NULL,
                creado    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)


try:
    iniciar_bd()
except Exception as e:  # la app arranca igual y muestra el error en la página
    print(f"[AVISO] No se pudo preparar la base de datos: {e}", file=sys.stderr)


def leer_formulario():
    datos = {c: request.form.get(c, "").strip()
             for c in ("nombre", "apellido", "cedula", "telefono", "carrera")}
    if not all(datos.values()):
        raise ValueError("Todos los campos son obligatorios.")
    if datos["carrera"] not in CARRERAS:
        raise ValueError("Escoge una carrera de la lista.")
    return datos


# ---------------------------------------------------------------------------
# Rutas
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    usuarios, error_bd, editando = [], None, None
    try:
        with conectar() as con, con.cursor() as cur:
            cur.execute("SELECT * FROM usuarios ORDER BY id")
            usuarios = cur.fetchall()
            editar_id = request.args.get("editar", type=int)
            if editar_id:
                cur.execute("SELECT * FROM usuarios WHERE id = %s", (editar_id,))
                editando = cur.fetchone()
    except Exception as e:
        error_bd = str(e)
    return render_template("index.html", instancia=INSTANCIA, usuarios=usuarios,
                           total=len(usuarios), carreras=CARRERAS,
                           editando=editando, error_bd=error_bd)


@app.route("/crear", methods=["POST"])
def crear():
    try:
        d = leer_formulario()
        with conectar() as con, con.cursor() as cur:
            cur.execute(
                "INSERT INTO usuarios (nombre, apellido, cedula, telefono, carrera) "
                "VALUES (%s, %s, %s, %s, %s)",
                (d["nombre"], d["apellido"], d["cedula"], d["telefono"], d["carrera"]))
        flash(f"Usuario {d['nombre']} {d['apellido']} creado.", "success")
    except pymysql.err.IntegrityError:
        flash("Ya existe un usuario con esa cédula.", "danger")
    except Exception as e:
        flash(f"No se pudo crear: {e}", "danger")
    return redirect(url_for("index"))


@app.route("/actualizar/<int:uid>", methods=["POST"])
def actualizar(uid):
    try:
        d = leer_formulario()
        with conectar() as con, con.cursor() as cur:
            cur.execute(
                "UPDATE usuarios SET nombre=%s, apellido=%s, cedula=%s, telefono=%s, carrera=%s "
                "WHERE id=%s",
                (d["nombre"], d["apellido"], d["cedula"], d["telefono"], d["carrera"], uid))
        flash("Usuario modificado.", "success")
    except pymysql.err.IntegrityError:
        flash("Ya existe otro usuario con esa cédula.", "danger")
    except Exception as e:
        flash(f"No se pudo modificar: {e}", "danger")
    return redirect(url_for("index"))


@app.route("/eliminar/<int:uid>", methods=["POST"])
def eliminar(uid):
    try:
        with conectar() as con, con.cursor() as cur:
            cur.execute("DELETE FROM usuarios WHERE id = %s", (uid,))
        flash("Usuario eliminado.", "success")
    except Exception as e:
        flash(f"No se pudo eliminar: {e}", "danger")
    return redirect(url_for("index"))


# Código que corre cada proceso de estrés: un ciclo vacío hasta que se acabe el tiempo
_QUEMAR_CPU = "import time,sys\nfin=time.time()+int(sys.argv[1])\nwhile time.time()<fin: pass"


@app.route("/stress")
def stress():
    """Pone todos los núcleos de ESTA instancia al 100 % durante N segundos.
    Ejemplo: /stress?segundos=300  (máximo 900)."""
    segundos = max(10, min(request.args.get("segundos", 300, type=int), 900))
    nucleos = os.cpu_count() or 1
    for _ in range(nucleos):
        subprocess.Popen([sys.executable, "-c", _QUEMAR_CPU, str(segundos)],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
    flash(f"Estrés iniciado en {INSTANCIA['id']}: {nucleos} núcleo(s) al 100 % "
          f"durante {segundos} s.", "warning")
    return redirect(url_for("index"))


if __name__ == "__main__":
    # Solo para pruebas en tu PC. En AWS la app corre con gunicorn (ver scripts/user_data.sh)
    app.run(host="0.0.0.0", port=5000, debug=True)
