REPO_URL="https://github.com/TU_USUARIO/proyecto-telematica-aws.git"   
DB_HOST="TU-ENDPOINT.xxxxxxxx.us-east-1.rds.amazonaws.com"             
DB_PASSWORD="TU_CONTRASEÑA_RDS"                                         
SECRET_KEY="pon-aqui-una-frase-larga-cualquiera"                         
DB_USER="admin"
DB_NAME="telematica"

exec > /var/log/user-data.log 2>&1   # todo lo que pase queda en este log (útil si algo falla)
set -x

# 1. Paquetes del sistema
dnf install -y git python3-pip

# 2. Descargar el código
git clone "$REPO_URL" /opt/app
cd /opt/app

# 3. Librerías de Python
pip3 install -r requirements.txt

# 4. Credenciales (fuera del repo, solo en el servidor)
cat > /etc/app.env <<EOF
DB_HOST=$DB_HOST
DB_USER=$DB_USER
DB_PASSWORD=$DB_PASSWORD
DB_NAME=$DB_NAME
SECRET_KEY=$SECRET_KEY
EOF
chmod 600 /etc/app.env

# 5. Servicio systemd: la app arranca sola y se reinicia si se cae
cat > /etc/systemd/system/app.service <<'EOF'
[Unit]
Description=App Flask Proyecto Telematica
After=network-online.target
Wants=network-online.target

[Service]
EnvironmentFile=/etc/app.env
WorkingDirectory=/opt/app
ExecStart=/usr/bin/python3 -m gunicorn --workers 2 --bind 0.0.0.0:80 app:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now app.service
