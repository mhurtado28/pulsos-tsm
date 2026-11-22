"""Mapas con isolineas y series de tiempo por area.

Trabaja solo con horas nocturnas (00-06 h local) para evitar el calentamiento
diurno, y arma un compuesto nocturno por dia.

Genera en figuras/:
  - diarios/mapa_YYYYmmdd.png       compuesto nocturno diario con isotermas y areas
  - series_areas.png                TSM por area, dT costa-referencia, fondo y eventos
  - series_noche_diaria.csv         series diarias, cobertura, fondo y anomalias
  - eventos.csv                     pulsos detectados: tipo, inicio, fin, duracion
  - horarios/ (solo con --horarios) un mapa por hora

Uso:
    python src/analizar.py
    python src/analizar.py --sin-mapas     # solo series y eventos (rapido)
    python src/analizar.py --horarios
"""
import argparse
import glob
import os
import sys

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import xarray as xr  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402
from scipy.ndimage import uniform_filter  # noqa: E402

sys.path.insert(0, os.path.dirname(__file__))
import config as C  # noqa: E402

ESCALA = os.environ.get("ESCALA_COSTA", "10m")
COLORES = ["#d62728", "#1f77b4", "#2ca02c", "#9467bd", "#ff7f0e"]


def cargar():
    archivos = sorted(glob.glob(os.path.join(C.DATA_DIR, "sst_*.nc")))
    if not archivos:
        sys.exit("No hay datos en data/. Corre primero src/descargar_goes.py")
    primeros = xr.load_dataset(archivos[0])
    primeros = primeros.drop_vars("time")
    lat, lon = primeros["lat"], primeros["lon"]
    sst = []
    for a in archivos:
        da = xr.load_dataset(a)["sst"]
        t = da["time"].values
        sst.append(da.drop_vars(["lat", "lon", "time"]).expand_dims(time=[t]))
    ds = xr.concat(sst, dim="time").to_dataset(name="sst")
    return ds.assign_coords(lat=lat, lon=lon)


def suavizar(campo, n=5):
    """Media movil n x n que ignora NaN (solo para trazar isolineas)."""
    ok = np.isfinite(campo)
    num = uniform_filter(np.where(ok, campo, 0.0), n)
    den = uniform_filter(ok.astype(float), n)
    with np.errstate(invalid="ignore", divide="ignore"):
        out = num / den
    out[den < 0.5] = np.nan
    return out


def mapa(sst2d, lat, lon, titulo, salida):
    fig = plt.figure(figsize=(9, 7))
    ax = plt.axes(projection=ccrs.PlateCarree())
    ax.set_extent(C.DOMINIO, crs=ccrs.PlateCarree())
    niveles = np.arange(C.TSM_RANGO[0], C.TSM_RANGO[1] + 1e-6, C.ISO_INTERVALO)
    pc = ax.pcolormesh(lon, lat, sst2d, cmap="RdYlBu_r", vmin=C.TSM_RANGO[0],
                       vmax=C.TSM_RANGO[1], shading="auto", transform=ccrs.PlateCarree())
    if np.isfinite(sst2d).sum() > 50:
        cs = ax.contour(lon, lat, suavizar(sst2d), levels=niveles, colors="k", linewidths=0.6,
                        transform=ccrs.PlateCarree())
        ax.clabel(cs, cs.levels[::2], fmt="%.1f", fontsize=7)
    if ESCALA != "none":
        ax.add_feature(cfeature.LAND.with_scale(ESCALA), facecolor="0.85", zorder=2)
        ax.add_feature(cfeature.COASTLINE.with_scale(ESCALA), linewidth=0.7, zorder=3)
    for (nombre, (lo0, lo1, la0, la1)), col in zip(C.AREAS.items(), COLORES):
        ax.add_patch(Rectangle((lo0, la0), lo1 - lo0, la1 - la0, fill=False, ec=col,
                               lw=2, transform=ccrs.PlateCarree(), zorder=4))
        ax.text(lo0, la1 + 0.05, nombre, color=col, fontsize=8, weight="bold",
                transform=ccrs.PlateCarree(), zorder=5)
    gl = ax.gridlines(draw_labels=True, linewidth=0.3, color="0.5")
    gl.top_labels = gl.right_labels = False
    plt.colorbar(pc, ax=ax, shrink=0.8, label="TSM (°C)")
    valid = np.isfinite(sst2d).mean()
    ax.set_title(f"{titulo}   (píxeles válidos: {valid:.0%})")
    fig.savefig(salida, dpi=130, bbox_inches="tight")
    plt.close(fig)


def cobertura_y_media(campo, mar, caja, lat, lon):
    """Media de la caja y fraccion de pixeles de mar con dato."""
    lo0, lo1, la0, la1 = caja
    m = (lon >= lo0) & (lon <= lo1) & (lat >= la0) & (lat <= la1) & mar
    v = campo.where(m)
    return v.mean(("y", "x")).values, (np.isfinite(v).sum(("y", "x")) / m.sum()).values


def detectar(serie, fondo):
    """Eventos donde la anomalia (serie - fondo) supera +/- UMBRAL_PULSO.

    relajacion:      dT sube (surgencia mas debil que lo normal)
    intensificacion: dT baja (surgencia mas fuerte que lo normal)
    """
    anom = (serie - fondo).interpolate(limit=C.MAX_HUECO_DIAS, limit_area="inside")
    eventos = []
    for tipo, signo in (("relajacion", 1), ("intensificacion", -1)):
        activo = (signo * anom) > C.UMBRAL_PULSO
        grupo = (activo != activo.shift()).cumsum()
        for _, g in anom[activo].groupby(grupo[activo]):
            obs = serie.loc[g.index].notna()          # recorta dias interpolados en los bordes
            if not obs.any():
                continue
            g = g.loc[obs.idxmax():obs[::-1].idxmax()]
            eventos.append({
                "tipo": tipo,
                "inicio": g.index[0].date(),
                "fin": g.index[-1].date(),
                "duracion_dias": len(g),
                "anomalia_max_C": round(float(signo * (signo * g).max()), 2),
                "dias_interpolados": int(serie.loc[g.index].isna().sum()),
            })
    return anom, eventos


def series(diario, lat, lon):
    mar = np.isfinite(diario).any("time")
    tabla = {}
    for nombre, caja in C.AREAS.items():
        media, cob = cobertura_y_media(diario, mar, caja, lat, lon)
        tabla[nombre] = media
        tabla[f"cob {nombre}"] = cob
    df = pd.DataFrame(tabla, index=pd.to_datetime(diario.time.values))
    ref = "Referencia oceanica"
    costas = [n for n in C.AREAS if n != ref]
    for nombre in C.AREAS:  # control de calidad por cobertura
        df.loc[df[f"cob {nombre}"] < C.MIN_COBERTURA, nombre] = np.nan

    todos = []
    for n in costas:
        dT = df[n] - df[ref]
        fondo = dT.rolling(C.VENTANA_FONDO_DIAS, center=True, min_periods=5).median()
        anom, ev = detectar(dT, fondo)
        df[f"dT {n}"], df[f"fondo {n}"], df[f"anom {n}"] = dT, fondo, anom
        todos += [{"area": n, **e} for e in ev]
    eventos = pd.DataFrame(todos)
    df.to_csv(os.path.join(C.FIG_DIR, "series_noche_diaria.csv"), float_format="%.3f")
    eventos.to_csv(os.path.join(C.FIG_DIR, "eventos.csv"), index=False)

    fig, axs = plt.subplots(1 + len(costas), 1, figsize=(12, 3.2 * (1 + len(costas))), sharex=True)
    for nombre, col in zip(C.AREAS, COLORES):
        axs[0].plot(df.index, df[nombre], "o-", color=col, ms=3, lw=1.2, label=nombre)
    axs[0].set_ylabel("TSM (°C)")
    axs[0].legend(fontsize=8, ncol=3)
    axs[0].set_title("TSM nocturna (00–06 h local), compuesto diario por área")
    for ax, n, col in zip(axs[1:], costas, COLORES):
        ax.plot(df.index, df[f"dT {n}"], "o-", color=col, ms=3, lw=1.2, label="ΔT costa − ref")
        ax.plot(df.index, df[f"fondo {n}"], "k--", lw=1,
                label=f"fondo (mediana {C.VENTANA_FONDO_DIAS} d)")
        ax.fill_between(df.index, df[f"fondo {n}"] - C.UMBRAL_PULSO,
                        df[f"fondo {n}"] + C.UMBRAL_PULSO, color="0.85",
                        label=f"± {C.UMBRAL_PULSO} °C")
        if len(eventos):
            for _, e in eventos[eventos.area == n].iterrows():
                c = "#f4a582" if e.tipo == "relajacion" else "#92c5de"
                ax.axvspan(pd.Timestamp(e.inicio) - pd.Timedelta("12h"),
                           pd.Timestamp(e.fin) + pd.Timedelta("12h"), color=c, alpha=0.5)
        ax.set_ylabel("ΔT (°C)")
        ax.set_title(f"{n}: naranja = relajación, azul = intensificación")
        ax.legend(fontsize=7, loc="lower left")
    fig.autofmt_xdate()
    fig.savefig(os.path.join(C.FIG_DIR, "series_areas.png"), dpi=130, bbox_inches="tight")
    plt.close(fig)
    return df, eventos


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--horarios", action="store_true", help="tambien un mapa por cada hora")
    ap.add_argument("--sin-mapas", action="store_true", help="solo series y eventos")
    ap.add_argument("--sin-horarios", action="store_true", help=argparse.SUPPRESS)
    args = ap.parse_args()

    ds = cargar()
    ds = ds.sel(time=pd.to_datetime(ds.time.values).hour.isin(C.HORAS_NOCHE_UTC))
    lat, lon = ds.lat, ds.lon
    for sub in ("horarios", "diarios"):
        os.makedirs(os.path.join(C.FIG_DIR, sub), exist_ok=True)

    if args.horarios:
        for t in ds.time.values:
            ts = pd.Timestamp(t)
            mapa(ds.sst.sel(time=t).values, lat.values, lon.values,
                 f"GOES-16 TSM {ts:%Y-%m-%d %H} UTC",
                 os.path.join(C.FIG_DIR, "horarios", f"mapa_{ts:%Y%m%d_%H}.png"))

    diario = ds.sst.resample(time="1D").mean()
    if not args.sin_mapas:
        for t in diario.time.values:
            ts = pd.Timestamp(t)
            mapa(diario.sel(time=t).values, lat.values, lon.values,
                 f"GOES-16 TSM nocturna {ts:%Y-%m-%d}",
                 os.path.join(C.FIG_DIR, "diarios", f"mapa_{ts:%Y%m%d}.png"))

    df, eventos = series(diario, lat, lon)
    print(f"Dias: {len(df)}  |  descartados por nubes (cob < {C.MIN_COBERTURA:.0%}):")
    for n in C.AREAS:
        print(f"   {n}: {int(df[n].isna().sum())}")
    if len(eventos):
        print("\nEventos detectados:")
        print(eventos.to_string(index=False))
        print("\nResumen por area y tipo (duracion en dias):")
        print(eventos.groupby(["area", "tipo"])["duracion_dias"]
              .agg(["count", "mean", "min", "max"]).round(1).to_string())
    else:
        print("\nNo se detectaron eventos con el umbral actual.")


if __name__ == "__main__":
    main()
