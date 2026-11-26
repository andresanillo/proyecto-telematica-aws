#!/bin/bash
# Estrés por SSH (respaldo de la ruta /stress). Pone todos los núcleos al 100 %.
# Uso, dentro de la EC2:   bash estres.sh 300      (segundos, por defecto 300)
# Para cortarlo antes:     sudo pkill yes
SEGUNDOS=${1:-300}
NUCLEOS=$(nproc)
echo "Estresando $NUCLEOS núcleo(s) durante $SEGUNDOS s... (mira la CPU con: top)"
for i in $(seq "$NUCLEOS"); do
  timeout "$SEGUNDOS" yes > /dev/null &
done
wait
echo "Listo, estrés terminado."
