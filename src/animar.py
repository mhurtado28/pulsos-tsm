"""Animaciones de la TSM.

1) Diaria: un cuadro por dia (compuesto nocturno 00-06 h local), todo el periodo.
2) Horaria: una animacion por cada cambio relevante. Para cada uno descarga TODAS
   las horas de la ventana (no solo la noche) y muestra el mapa hora a hora junto
   con la serie horaria de dT costa - referencia.

Cambios relevantes (por orden de importancia, maximo N_EVENTOS_HORARIOS):
  - eventos de figuras/eventos.csv (relajacion / intensificacion, de analizar.py)
  - saltos de dT de un dia al siguiente mayores que SALTO_MIN_C en
    figuras/series_noche_diaria.csv

Uso:
    python src/analizar.py            # primero, para tener eventos y series
    python src/animar.py              # diaria + horarias
    python src/animar.py --solo-diaria
    python src/animar.py --solo-horaria
"""
import argparse
import os
import shutil
import sys

import cartopy.crs as ccrs
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from PIL import Image  # noqa: E402

sys.path.insert(0, os.path.dirname(__file__))
import analizar as A  # noqa: E402
import config as C  # noqa: E402
import descargar_goes as D  # noqa: E402

ANIM_DIR = os.path.join(C.FIG_DIR, "animaciones")
N_EVENTOS_HORARIOS = 4      # maximo de animaciones horarias
DIAS_ANTES_DESPUES = 2      # dias de contexto alrededor de cada evento
SALTO_MIN_C = 0.4           # salto diario minimo de dT para contar como cambio relevante
MS_DIARIO = 600             # milisegundos por cuadro
MS_HORARIO = 250
DPI = 72


def gif(cuadros, salida, ms):
    imgs = [Image.open(c).convert("RGB") for c in cuadros]
    w, h = imgs[0].size
    # paleta comun de 128 colores: archivos mucho mas livianos
    paleta = imgs[len(imgs) // 2].resize((w, h)).quantize(colors=128)
    imgs = [i.resize((w, h)).quantize(palette=paleta, dither=Image.Dither.NONE) for i in imgs]
    imgs[0].save(salida, save_all=True, append_images=imgs[1:], duration=ms, loop=0,
                 optimize=True)
    print(f"[gif] {salida}  ({len(imgs)} cuadros)")


# ---------------------------------------------------------------- diaria
def animacion_diaria():
    ds = A.cargar()
    ds = ds.sel(time=pd.to_datetime(ds.time.values).hour.isin(C.HORAS_NOCHE_UTC))
    diario = ds.sst.resample(time="1D").mean()
    tmp = os.path.join(ANIM_DIR, "_cuadros_diaria")
    os.makedirs(tmp, exist_ok=True)
    cuadros = []
    for t in diario.time.values:
        ts = pd.Timestamp(t)
        f = os.path.join(tmp, f"{ts:%Y%m%d}.png")
        A.mapa(diario.sel(time=t).values, ds.lat.values, ds.lon.values,
               f"TSM nocturna {ts:%Y-%m-%d}", f, dpi=DPI)
        cuadros.append(f)
    gif(cuadros, os.path.join(ANIM_DIR, f"diaria_{C.FECHA_INICIO}_{C.FECHA_FIN}.gif"), MS_DIARIO)
    shutil.rmtree(tmp)


# ---------------------------------------------------------------- horaria
def cambios_relevantes():
    """Lista de (nombre, area, inicio, fin) ordenada por importancia."""
    cambios = []
    f_ev = os.path.join(C.FIG_DIR, "eventos.csv")
    if os.path.exists(f_ev) and os.path.getsize(f_ev) > 1:
        ev = pd.read_csv(f_ev, parse_dates=["inicio", "fin"])
        ev = ev.reindex(ev.anomalia_max_C.abs().sort_values(ascending=False).index)
        for _, e in ev.iterrows():
            cambios.append((f"{e.tipo}_{e.area.split()[0].lower()}", e.area, e.inicio, e.fin,
                            abs(e.anomalia_max_C)))
    f_se = os.path.join(C.FIG_DIR, "series_noche_diaria.csv")
    if os.path.exists(f_se):
        df = pd.read_csv(f_se, index_col=0, parse_dates=True)
        for col in [c for c in df.columns if c.startswith("dT ")]:
            area = col[3:]
            salto = df[col].diff()
            for t, v in salto[salto.abs() > SALTO_MIN_C].items():
                tipo = "salto_relajacion" if v > 0 else "salto_intensificacion"
                cambios.append((f"{tipo}_{area.split()[0].lower()}", area,
                                t - pd.Timedelta("1D"), t, abs(v)))
    # quitar cambios que se solapan con uno mas importante (misma area o no)
    elegidos = []
    for c in sorted(cambios, key=lambda c: -c[4]):
        if all(c[3] < e[2] - pd.Timedelta("1D") or c[2] > e[3] + pd.Timedelta("1D")
               for e in elegidos):
            elegidos.append(c)
        if len(elegidos) == N_EVENTOS_HORARIOS:
            break
    return elegidos


def series_horarias(ds):
    """dT horario costa - referencia, y TSM por area."""
    mar = np.isfinite(ds.sst).any("time")
    tabla = {}
    for nombre, caja in C.AREAS.items():
        media, cob = A.cobertura_y_media(ds.sst, mar, caja, ds.lat, ds.lon)
        media = np.where(cob >= C.MIN_COBERTURA, media, np.nan)
        tabla[nombre] = media
    df = pd.DataFrame(tabla, index=pd.to_datetime(ds.time.values))
    ref = "Referencia oceanica"
    for n in C.AREAS:
        if n != ref:
            df[f"dT {n}"] = df[n] - df[ref]
    return df


def cuadro_horario(sst2d, lat, lon, t, df, evento, salida):
    fig = plt.figure(figsize=(10, 10))
    ax = fig.add_axes([0.05, 0.33, 0.85, 0.62], projection=ccrs.PlateCarree())
    local = t - pd.Timedelta("5h")
    pc = A.dibujar_mapa(ax, sst2d, lat, lon,
                        f"{t:%Y-%m-%d %H} UTC  ({local:%d %b %H}h local)")
    cax = fig.add_axes([0.91, 0.40, 0.02, 0.48])
    fig.colorbar(pc, cax=cax, label="TSM (°C)")
    a2 = fig.add_axes([0.08, 0.05, 0.84, 0.22])
    for n, col in zip([c for c in df.columns if c.startswith("dT")], A.COLORES):
        a2.plot(df.index, df[n], ".-", color=col, ms=3, lw=0.8, label=n)
    # sombrear noches (00-06 h local) y el evento
    for d in pd.date_range(df.index[0].normalize(), df.index[-1].normalize(), freq="1D"):
        a2.axvspan(d + pd.Timedelta("5h"), d + pd.Timedelta("11h"), color="0.9", zorder=0)
    a2.axvspan(evento[2], evento[3] + pd.Timedelta("23h"), color="#fdd49e", alpha=0.5,
               zorder=0, label="evento")
    a2.axvline(t, color="k", lw=1.5)
    a2.set_ylabel("ΔT costa − ref (°C)")
    a2.legend(fontsize=7, loc="lower left", ncol=3)
    a2.set_title("gris = noche (00–06 h local); el día trae calentamiento diurno", fontsize=8)
    fig.savefig(salida, dpi=DPI)
    plt.close(fig)


def animacion_horaria(evento):
    nombre, area, ini, fin, _ = evento
    t0 = ini.normalize() - pd.Timedelta(days=DIAS_ANTES_DESPUES)
    t1 = fin.normalize() + pd.Timedelta(days=DIAS_ANTES_DESPUES, hours=23)
    print(f"\n== {nombre} ({area}): {ini:%Y-%m-%d} a {fin:%Y-%m-%d}; ventana {t0:%m-%d} a {t1:%m-%d}")
    horas = pd.date_range(t0, t1, freq="1h")
    D.descargar(horas)
    ds = A.cargar()
    ds = ds.sel(time=(ds.time >= np.datetime64(t0)) & (ds.time <= np.datetime64(t1)))
    df = series_horarias(ds)
    tmp = os.path.join(ANIM_DIR, f"_cuadros_{nombre}")
    os.makedirs(tmp, exist_ok=True)
    cuadros = []
    for t in ds.time.values:
        ts = pd.Timestamp(t)
        f = os.path.join(tmp, f"{ts:%Y%m%d_%H}.png")
        cuadro_horario(ds.sst.sel(time=t).values, ds.lat.values, ds.lon.values, ts, df, evento, f)
        cuadros.append(f)
    gif(cuadros, os.path.join(ANIM_DIR, f"horaria_{nombre}_{ini:%Y%m%d}.gif"), MS_HORARIO)
    shutil.rmtree(tmp)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--solo-diaria", action="store_true")
    ap.add_argument("--solo-horaria", action="store_true")
    args = ap.parse_args()
    os.makedirs(ANIM_DIR, exist_ok=True)

    if not args.solo_horaria:
        animacion_diaria()
    if not args.solo_diaria:
        cambios = cambios_relevantes()
        if not cambios:
            print("No hay cambios relevantes. Corre primero src/analizar.py")
        print("Cambios elegidos para animacion horaria:")
        for c in cambios:
            print(f"   {c[0]:32s} {c[1]:20s} {c[2]:%Y-%m-%d} a {c[3]:%Y-%m-%d}  |{c[4]:.2f}| C")
        for c in cambios:
            animacion_horaria(c)


if __name__ == "__main__":
    main()
