"""Configuracion comun: periodo, dominio y areas de analisis."""

# Periodo por defecto: enero-marzo 2023 (epoca seca, alisios fuertes).
# Se cambia por linea de comandos en todos los scripts: --inicio 2018-01-01 --fin 2018-03-31
FECHA_INICIO = "2023-01-01"
FECHA_FIN = "2023-03-31"          # inclusive
SATELITE = "goes16"              # GOES-East en 2023 (GOES-19 se lanzo en 2024)
PRODUCTO = "ABI-L2-SSTF"         # TSM Full Disk, horaria, ~2 km
PASO_HORAS = 1                   # 1 = todas las horas; 2 o 3 para bajar menos

# Dominio de recorte (lon_min, lon_max, lat_min, lat_max)
DOMINIO = (-75.5, -70.5, 10.0, 14.0)

# Areas donde se esperan cambios (lon_min, lon_max, lat_min, lat_max)
AREAS = {
    # Nucleo de surgencia: desde la lengua fria al W del Cabo de la Vela hasta
    # pasar Punta Gallinas, con mas mar al norte (~3200 pixeles de mar)
    "Nucleo Guajira": (-72.9, -71.3, 11.8, 12.8),
    # Franja costera occidental Riohacha-Palomino
    "Riohacha": (-73.6, -72.7, 11.2, 11.9),
    # Referencia oceanica: al NW, fuera de la lengua y los filamentos frios,
    # con un numero de pixeles de mar similar al nucleo (~3300)
    "Referencia oceanica": (-75.3, -74.0, 13.1, 14.0),
}

# Calidad: DQF == 0 es "good quality" en ABI-L2-SST
DQF_VALIDOS = (0,)
# Rango fisico de TSM en la zona: fuera de el son bordes de nube mal enmascarados
TSM_MIN_VALIDA = 20.0
TSM_MAX_VALIDA = 32.0

# Isolineas
ISO_INTERVALO = 0.5  # grados C
TSM_RANGO = (23.0, 28.5)

# Horas nocturnas (UTC) para evitar el calentamiento diurno: 00-06 h local (UTC-5)
HORAS_NOCHE_UTC = (5, 6, 7, 8, 9, 10)
# Horas que se descargan (None = todas). Por defecto solo la noche: 6 archivos/dia
HORAS_DESCARGA_UTC = HORAS_NOCHE_UTC

# Control de calidad del compuesto nocturno diario: fraccion minima de pixeles de
# mar con dato en la caja (mar = pixeles con dato al menos una vez en el periodo)
MIN_COBERTURA = 0.25

# Serie usada para detectar pulsos (compuesto nocturno diario):
#   "tsm": TSM promedio de cada area costera (sube = relajacion, baja = intensificacion)
#   "dT":  TSM costa - TSM referencia oceanica
SERIE = "tsm"
# Deteccion de pulsos
VENTANA_FONDO_DIAS = 31     # dias usados para el estado "normal" de la surgencia
TIPO_FONDO = "previo"       # "previo": mediana de los 31 dias anteriores; "centrado"
MIN_DIAS_EVENTO = 2         # dias seguidos minimos para contar un evento
UMBRAL_PULSO = 0.5          # grados C de anomalia respecto al fondo
MAX_HUECO_DIAS = 1          # huecos (nubes) de hasta 1 dia se interpolan para detectar

DATA_DIR = "data"                 # comun a todos los periodos (archivos por fecha y hora)
FIG_BASE = "figuras"
FIG_DIR = f"{FIG_BASE}/{FECHA_INICIO}_{FECHA_FIN}"   # salidas separadas por periodo
DESCARGAS_PARALELAS = 8


def agregar_args_periodo(ap):
    ap.add_argument("--inicio", default=FECHA_INICIO, help="AAAA-MM-DD")
    ap.add_argument("--fin", default=FECHA_FIN, help="AAAA-MM-DD (inclusive)")


def aplicar_periodo(args):
    """Fija el periodo y la carpeta de salida figuras/<inicio>_<fin>/."""
    global FECHA_INICIO, FECHA_FIN, FIG_DIR
    FECHA_INICIO, FECHA_FIN = args.inicio, args.fin
    FIG_DIR = f"{FIG_BASE}/{FECHA_INICIO}_{FECHA_FIN}"
    import os
    os.makedirs(FIG_DIR, exist_ok=True)
    print(f"Periodo {FECHA_INICIO} a {FECHA_FIN}  ->  {FIG_DIR}/")
