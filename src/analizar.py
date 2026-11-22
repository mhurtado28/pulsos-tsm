"""Mapas con isolineas y series de tiempo por area.

Genera en figuras/:
  - horarios/mapa_YYYYmmdd_HH.png   mapa de cada hora con isotermas y areas
  - diarios/mapa_YYYYmmdd.png       compuesto diario (media de horas validas)
  - series_areas.png                TSM media por area + diferencia costa-oceano
  - series_areas.csv                los mismos datos en tabla

Uso:
    python src/analizar.py            # todo
    python src/analizar.py --sin-horarios
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


def media_area(ds, caja):
    lo0, lo1, la0, la1 = caja
    m = (ds.lon >= lo0) & (ds.lon <= lo1) & (ds.lat >= la0) & (ds.lat <= la1)
    v = ds["sst"].where(m)
    return v.mean(("y", "x")), np.isfinite(v).sum(("y", "x")) / m.sum()


def series(ds):
    tabla = {}
    for nombre, caja in C.AREAS.items():
        media, frac = media_area(ds, caja)
        tabla[nombre] = media.values
        tabla[f"{nombre} (frac. valida)"] = frac.values  # incluye tierra en el denominador
    df = pd.DataFrame(tabla, index=pd.to_datetime(ds.time.values))
    ref = "Referencia oceanica"
    for nombre in C.AREAS:
        if nombre != ref:
            df[f"dT {nombre} - ref"] = df[nombre] - df[ref]
    df.to_csv(os.path.join(C.FIG_DIR, "series_areas.csv"), float_format="%.3f")

    fig, (a1, a2) = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
    for nombre, col in zip(C.AREAS, COLORES):
        a1.plot(df.index, df[nombre], ".-", color=col, ms=3, lw=0.8, label=nombre)
        d = df[nombre].resample("1D").mean()
        d.index = d.index + pd.Timedelta("12h")
        a1.plot(d, "o-", color=col, lw=2, ms=5, alpha=0.6)
    a1.set_ylabel("TSM media (°C)")
    a1.legend(fontsize=8)
    a1.set_title("TSM horaria (puntos) y media diaria (línea gruesa) por área")
    noche = df[df.index.hour.isin(C.HORAS_NOCHE_UTC)].resample("1D").mean()
    noche.index = noche.index + pd.Timedelta("8h")  # centro de la ventana nocturna (08 UTC)
    for c, col in zip([c for c in df.columns if c.startswith("dT")], COLORES):
        a2.plot(df.index, df[c], ".-", color=col, ms=2, lw=0.6, alpha=0.5, label=f"{c} (horario)")
        a2.plot(noche.index, noche[c], "s-", color=col, lw=2, ms=6,
                label=f"{c} (noche 00-06 h local)")
    a2.axhline(0, color="k", lw=0.5)
    a2.set_ylabel("ΔT costa − océano (°C)")
    a2.legend(fontsize=7, ncol=2)
    a2.set_title("Índice de surgencia por TSM (más negativo = surgencia más intensa)")
    fig.autofmt_xdate()
    fig.savefig(os.path.join(C.FIG_DIR, "series_areas.png"), dpi=130, bbox_inches="tight")
    plt.close(fig)
    noche.to_csv(os.path.join(C.FIG_DIR, "series_noche_diaria.csv"), float_format="%.3f")
    return df, noche


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sin-horarios", action="store_true")
    args = ap.parse_args()

    ds = cargar()
    lat, lon = ds.lat.values, ds.lon.values
    for sub in ("horarios", "diarios"):
        os.makedirs(os.path.join(C.FIG_DIR, sub), exist_ok=True)

    if not args.sin_horarios:
        for t in ds.time.values:
            ts = pd.Timestamp(t)
            mapa(ds.sst.sel(time=t).values, lat, lon, f"GOES-16 TSM {ts:%Y-%m-%d %H} UTC",
                 os.path.join(C.FIG_DIR, "horarios", f"mapa_{ts:%Y%m%d_%H}.png"))

    diario = ds.sst.resample(time="1D").mean()
    for t in diario.time.values:
        ts = pd.Timestamp(t)
        mapa(diario.sel(time=t).values, lat, lon, f"GOES-16 TSM media diaria {ts:%Y-%m-%d}",
             os.path.join(C.FIG_DIR, "diarios", f"mapa_{ts:%Y%m%d}.png"))

    df, noche = series(ds)
    cols = [c for c in df.columns if "frac" not in c]
    print("Media diaria (todas las horas):")
    print(df[cols].resample("1D").mean().round(2).to_string())
    print("\nMedia diaria solo noche (00-06 h local):")
    print(noche[cols].round(2).to_string())


if __name__ == "__main__":
    main()
