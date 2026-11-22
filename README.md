# pulsos-tsm

Exploración de **pulsos de surgencia** en La Guajira (Caribe colombiano) con TSM horaria del satélite geoestacionario GOES (ABI-L2-SSTF, ~2 km).

Objetivo: ver si la surgencia ocurre en pulsos cortos y estimar cuánto duran, comparando la TSM en el núcleo de surgencia contra una referencia oceánica.

## Datos

- **Producto:** `ABI-L2-SSTF` (TSM Full Disk, **horaria**, ~2 km en el nadir), en el bucket público de NOAA en AWS (`noaa-goes16`). Se accede sin cuenta.
- **Satélite:** GOES-16. Fue GOES-East hasta abril de 2025 (GOES-19 se lanzó en 2024 y no tiene datos de 2023).
- **Resolución temporal:** la TSM de nivel 2 se publica cada hora, no hay producto de 30 minutos. Para bajar menos archivos, cambia `PASO_HORAS` en `src/config.py`.
- **Calidad:** solo se usan los píxeles con `DQF == 0` (buena calidad). Las nubes dejan huecos.
- **Periodo por defecto:** enero y febrero de 2023 (época seca, con alisios fuertes).
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

python src/descargar_goes.py              # recorta y guarda data/sst_YYYYmmdd_HH.nc
python src/analizar.py                    # mapas diarios + series + eventos
python src/analizar.py --sin-mapas        # solo series y eventos (rápido)
python src/analizar.py --horarios         # además un mapa por hora
```

## Método

1. **Compuesto nocturno diario:** media por píxel de las horas de 00 a 06 h local.
2. **Control de calidad:** si en una caja hay menos de `MIN_COBERTURA` (25%) de píxeles de mar con dato, ese día se descarta. El mar se define como los píxeles que tuvieron dato al menos una vez en el periodo.
3. **Índice de surgencia:** ΔT = TSM(costa) − TSM(referencia oceánica). Más negativo significa surgencia más intensa.
4. **Fondo:** mediana móvil centrada de `VENTANA_FONDO_DIAS` (15) días. Representa el estado "normal" de la surgencia.
5. **Pulsos:** días seguidos en que la anomalía (ΔT − fondo) supera ±`UMBRAL_PULSO` (0,5 °C).
   - **Relajación:** ΔT sube; la surgencia se debilita.
   - **Intensificación:** ΔT baja; la surgencia se intensifica.

   Los huecos por nubes de hasta 1 día se interpolan para no cortar un evento, pero no cuentan si caen en los bordes. La resolución de la duración es de 1 día.

## Salidas (`figuras/`)

- `series_areas.png`: TSM nocturna por área y, para cada zona costera, ΔT con su fondo, la banda de ±0,5 °C y los eventos sombreados (naranja = relajación, azul = intensificación).
- `eventos.csv`: un evento por fila, con área, tipo, inicio, fin, duración en días, anomalía máxima y días interpolados.
- `series_noche_diaria.csv`: series diarias, cobertura, fondo y anomalía.
- `diarios/mapa_*.png`: compuesto nocturno de cada día con isotermas cada 0,5 °C y las áreas. Las isotermas se trazan sobre un campo suavizado 5×5.
