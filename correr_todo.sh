#!/usr/bin/env bash
# Corre descarga + analisis + animaciones para los periodos indicados.
# Uso:  bash correr_todo.sh                 (ene-mar 2023 y ene-mar 2018)
#       bash correr_todo.sh 2019-01-01:2019-03-31
set -e
PERIODOS=${@:-"2023-01-01:2023-03-31 2018-01-01:2018-03-31"}
for P in $PERIODOS; do
  INI=${P%%:*}; FIN=${P##*:}
  echo "==================== $INI a $FIN ===================="
  python src/descargar_goes.py --inicio "$INI" --fin "$FIN"
  python src/analizar.py       --inicio "$INI" --fin "$FIN"
  python src/animar.py         --inicio "$INI" --fin "$FIN"
done
echo "Listo. Resultados en figuras/<inicio>_<fin>/"
