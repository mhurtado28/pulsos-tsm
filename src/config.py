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
    # Nucleo de surgencia (Gutierrez Leones et al. 2015, Bol. Cient. CIOH)
    "Nucleo Guajira": (-72.7, -71.6, 11.7, 12.6),
    # Franja costera occidental Riohacha-Palomino
    "Riohacha": (-73.6, -72.7, 11.2, 11.9),
    # Referencia oceanica (fuera de la influencia directa de la surgencia)
    "Referencia oceanica": (-73.0, -72.0, 13.0, 13.6),
}

# Calidad: DQF == 0 es "good quality" en ABI-L2-SST
DQF_VALIDOS = (0,)

# Isolineas
ISO_INTERVALO = 0.5  # grados C
TSM_RANGO = (23.0, 28.5)

DATA_DIR = "data"
FIG_DIR = "figuras"
