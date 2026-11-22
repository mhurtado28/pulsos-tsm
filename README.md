# pulsos-tsm

Exploración de **pulsos de surgencia** en La Guajira (Caribe colombiano) con TSM horaria del satélite geoestacionario GOES (ABI-L2-SSTF, ~2 km).

Objetivo: ver si la surgencia ocurre en pulsos cortos y estimar cuánto duran, comparando la TSM en el núcleo de surgencia contra una referencia oceánica.

## Datos

- **Producto:** `ABI-L2-SSTF` (TSM Full Disk, **horaria**, ~2 km en el nadir), en el bucket público de NOAA en AWS (`noaa-goes16`). Se accede sin cuenta.
- **Satélite:** GOES-16. Fue GOES-East hasta abril de 2025 (GOES-19 se lanzó en 2024 y no tiene datos de 2023).
- **Resolución temporal:** la TSM de nivel 2 se publica cada hora, no hay producto de 30 minutos. Para bajar menos archivos, cambia `PASO_HORAS` en `src/config.py`.
- **Calidad:** solo se usan los píxeles con `DQF == 0` (buena calidad). Las nubes dejan huecos.
- **Periodo por defecto:** 2023-02-06 a 2023-02-12 (época seca, con alisios fuertes).

El script lee por rangos solo la ventana del dominio, así que no baja el disco completo.

## Áreas

| Área | Lon | Lat |
|---|---|---|
| Núcleo Guajira (Gutiérrez Leones et al. 2015) | 72.7–71.6 W | 11.7–12.6 N |
| Riohacha (franja costera occidental) | 73.6–72.7 W | 11.2–11.9 N |
| Referencia oceánica | 73.0–72.0 W | 13.0–13.6 N |

Se editan en `src/config.py`.

## Uso (Codespace)

```bash
# el Codespace instala las dependencias solo; si no:
pip install -r requirements.txt

python src/descargar_goes.py      # recorta y guarda data/sst_YYYYmmdd_HH.nc
python src/analizar.py            # mapas + series
python src/analizar.py --sin-horarios   # solo mapas diarios + series
```

## Salidas (`figuras/`)

- `horarios/mapa_*.png`: TSM de cada hora con isotermas cada 0,5 °C y las áreas.
- `diarios/mapa_*.png`: compuesto diario (media de las horas válidas).
- `series_areas.png` / `.csv`: TSM media por área y ΔT costa − océano, horaria y diaria. Un pulso de surgencia aparece como una caída de ΔT. Su duración se lee directamente en la serie.

Las isotermas se trazan sobre un campo suavizado 5×5 (ignorando NaN) para reducir el ruido de píxel. El color muestra el dato original.
