"""Configuracion comun: periodo, dominio y areas de analisis."""

# Semana de febrero de 2023 (epoca seca, alisios fuertes -> surgencia activa)
FECHA_INICIO = "2023-02-06"
FECHA_FIN = "2023-02-12"          # inclusive
SATELITE = "goes16"              # GOES-East en 2023 (GOES-19 se lanzo en 2024)
PRODUCTO = "ABI-L2-SSTF"         # TSM Full Disk, horaria, ~2 km
PASO_HORAS = 1                   # 1 = todas las horas; 2 o 3 para bajar menos

# Dominio de recorte (lon_min, lon_max, lat_min, lat_max)
DOMINIO = (-75.5, -70.5, 10.0, 14.0)

# Areas donde se esperan cambios (lon_min, lon_max, lat_min, lat_max)
AREAS = {
    # Nucleo de surgencia al W del Cabo de la Vela, solo mar
    # (lengua fria < 23 C en los mapas de feb 2023)
    "Nucleo Guajira": (-72.9, -72.1, 11.8, 12.5),
    # Franja costera occidental Riohacha-Palomino
    "Riohacha": (-73.6, -72.7, 11.2, 11.9),
    # Referencia oceanica: al NW, fuera de la lengua y los filamentos frios
    # (la caja anterior, 73-72 W / 13-13.6 N, quedaba dentro de un filamento)
    "Referencia oceanica": (-75.0, -74.0, 13.2, 13.9),
}

# Calidad: DQF == 0 es "good quality" en ABI-L2-SST
DQF_VALIDOS = (0,)

# Isolineas
ISO_INTERVALO = 0.5  # grados C
TSM_RANGO = (23.0, 28.5)

# Horas nocturnas (UTC) para evitar el calentamiento diurno: 00-06 h local (UTC-5)
HORAS_NOCHE_UTC = (5, 6, 7, 8, 9, 10)

DATA_DIR = "data"
FIG_DIR = "figuras"
