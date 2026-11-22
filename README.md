# pulsos-tsm

Exploración de **pulsos de surgencia** en La Guajira (Caribe colombiano) con TSM horaria del satélite geoestacionario GOES (ABI-L2-SSTF, ~2 km).

Objetivo: ver si la surgencia ocurre en pulsos cortos y estimar cuánto duran, comparando la TSM en el núcleo de surgencia contra una referencia oceánica.

## Datos

- **Producto:** `ABI-L2-SSTF` (TSM Full Disk, **horaria**, ~2 km en el nadir), en el bucket público de NOAA en AWS (`noaa-goes16`). Se accede sin cuenta.
- **Satélite:** GOES-16. Fue GOES-East hasta abril de 2025 (GOES-19 se lanzó en 2024 y no tiene datos de 2023).
- **Resolución temporal:** la TSM de nivel 2 se publica cada hora, no hay producto de 30 minutos. Para bajar menos archivos, cambia `PASO_HORAS` en `src/config.py`.
- **Calidad:** solo se usan los píxeles con `DQF == 0` (buena calidad). Las nubes dejan huecos.
- **Periodo por defecto:** enero a marzo de 2023 (época seca, con alisios fuertes). Se cambia con `--inicio` y `--fin` en todos los scripts. Cada periodo guarda sus resultados en `figuras/<inicio>_<fin>/`.
- **2018:** GOES-16 ya era GOES-East desde diciembre de 2017, pero su producto de TSM se declaró de madurez provisional apenas el 9 de marzo de 2018 (beta antes de esa fecha). Los datos de enero y febrero de 2018 deben tomarse con más cautela y pueden tener horas faltantes.
- **Solo noche:** se descargan las horas de 00 a 06 h local (05–10 UTC), unos 354 archivos. Así se evita el calentamiento diurno, que en la tarde sube la TSM costera hasta ~1 °C y se confunde con un pulso. Se cambia con `HORAS_DESCARGA_UTC` en `src/config.py`.

El script lee por rangos solo la ventana del dominio, así que no baja el disco completo.

## Áreas

| Área | Lon | Lat | Píxeles de mar (aprox.) |
|---|---|---|---|
| Núcleo Guajira (Cabo de la Vela hasta pasar Punta Gallinas) | 72.9–71.3 W | 11.8–12.8 N | ~3200 |
| Riohacha (franja costera occidental) | 73.6–72.7 W | 11.2–11.9 N | ~1200 |
| Referencia oceánica (fuera de filamentos fríos) | 75.3–74.0 W | 13.1–14.0 N | ~3300 |

Las cajas son una elección de trabajo, no vienen de la literatura (la primera versión del núcleo seguía a Gutiérrez Leones et al. 2015). El núcleo y la referencia tienen un número parecido de píxeles de mar para que el ruido de sus promedios sea comparable.

`figuras/mapa_areas.png` muestra el recorte y las cajas.

Se editan en `src/config.py`.

## Uso (Codespace)

```bash
pip install -r requirements.txt   # si el Codespace no lo hizo solo

bash correr_todo.sh                       # ene-mar 2023 y ene-mar 2018: descarga + análisis + animaciones
bash correr_todo.sh 2019-01-01:2019-03-31 # otro periodo

# o por partes (el periodo por defecto es ene-mar 2023):
python src/descargar_goes.py --inicio 2018-01-01 --fin 2018-03-31
python src/descargar_goes.py              # recorta y guarda data/sst_YYYYmmdd_HH.nc
python src/analizar.py                    # mapas diarios + series + eventos
python src/analizar.py --sin-mapas        # solo series y eventos (rápido)
python src/analizar.py --horarios         # además un mapa por hora
python src/animar.py                      # animación diaria + horarias de los cambios relevantes
```

La descarga corre 8 procesos en paralelo (`DESCARGAS_PARALELAS` en `config.py`) y retoma donde quedó si se corta: los archivos ya bajados no se repiten.

**Codespace:** un Codespace se apaga solo tras 30 min de inactividad por defecto. Para corridas largas, sube el tiempo en GitHub → Settings → Codespaces → *Default idle timeout* (hasta 240 min).

## Animaciones (`figuras/<periodo>/animaciones/`)

`src/animar.py` (correrlo después de `analizar.py`):

- **Diaria:** `diaria_<inicio>_<fin>.gif`, un cuadro por día del compuesto nocturno.
- **Horaria, una por cambio relevante:** `horaria_<tipo>_<area>_<fecha>.gif`. Los cambios se toman de `eventos.csv` y de los saltos de ΔT entre días seguidos mayores de 0,4 °C. Primero entran los eventos detectados, ordenados por magnitud. Después entran los saltos cuya ventana no se solape con ningún evento ya elegido. Se dejan como máximo 4.
  - Para cada uno se descargan **todas** las horas desde 2 días antes hasta 2 días después del evento.
  - Cada cuadro muestra el mapa de esa hora y, abajo, la TSM promedio horaria de las tres áreas con el instante marcado.
  - En eventos de más de 3 días se anima solo el inicio, que es cuando ocurre el cambio.
  - En gris se marcan las horas nocturnas. Durante el día la TSM costera sube por calentamiento diurno, así que las subidas de la tarde no son pulsos.

## Método

1. **Compuesto nocturno diario:** media por píxel de las horas de 00 a 06 h local, solo con píxeles de buena calidad (`DQF = 0`).
2. **Control de calidad:** si en una caja hay menos de `MIN_COBERTURA` (25%) de píxeles de mar con dato, ese día se descarta. El mar se define como los píxeles que tuvieron dato al menos una vez en el periodo.
3. **Serie de cada área costera** (`SERIE = "tsm"`, por defecto): la TSM promedio del área, con dos versiones:
   - **media:** promedio de los píxeles de mar con dato.
   - **p10:** percentil 10, es decir, la temperatura del agua más fría del área.

   La referencia oceánica se grafica al lado para ver si toda la región se calienta o se enfría al mismo tiempo. Con `SERIE = "dT"` se usa en cambio la diferencia costa − referencia.
4. **Fondo:** mediana de los `VENTANA_FONDO_DIAS` (31) días **anteriores**, sin incluir el día (`TIPO_FONDO = "previo"`). Cada día se compara con el estado del mes previo. Así se detectan también relajaciones largas (1–2 semanas) y las que ocurren al final del periodo. Los primeros 7 días del periodo no tienen fondo. La opción `"centrado"` usa una mediana centrada, pero esa absorbe los eventos largos.
5. **Pulsos:** al menos `MIN_DIAS_EVENTO` (2) días seguidos en que la anomalía (serie − fondo) supera ±`UMBRAL_PULSO` (0,5 °C).
   - **Relajación:** la TSM del área sube; la surgencia se debilita.
   - **Intensificación:** la TSM del área baja; la surgencia se intensifica.

   Los huecos por nubes de hasta 1 día se interpolan para no cortar un evento, pero no cuentan si caen en los bordes. La resolución de la duración es de 1 día.

## Salidas (`figuras/<inicio>_<fin>/`)

- `series_areas.png`: TSM nocturna por área (media y P10) y, para cada zona costera y cada versión, la serie con su fondo, la banda de ±0,5 °C y los eventos sombreados (naranja = relajación, azul = intensificación).
- `eventos.csv`: un evento por fila, con área, índice, tipo, inicio, fin, duración en días, anomalía máxima y días interpolados.
- `series_noche_diaria.csv`: series diarias, cobertura, fondo y anomalía.
- `diarios/mapa_*.png`: compuesto nocturno de cada día con isotermas cada 0,5 °C y las áreas. Las isotermas se trazan sobre un campo suavizado 5×5.
