"""Descarga y recorta la TSM horaria de GOES (ABI-L2-SSTF) desde el bucket
publico de NOAA en AWS (acceso anonimo, sin cuenta).

Solo guarda el recorte del dominio: el archivo full disk no se baja completo,
xarray lee por rangos los bloques que caen dentro de la ventana.

Uso:
    python src/descargar_goes.py
"""
import os
import sys

import numpy as np
import pandas as pd
import s3fs
import xarray as xr

sys.path.insert(0, os.path.dirname(__file__))
import config as C  # noqa: E402


def latlon_goes(ds):
    """Lat/lon (grados) de la grilla fija geoestacionaria de ABI."""
    p = ds["goes_imager_projection"].attrs
    H = p["perspective_point_height"] + p["semi_major_axis"]
    r_eq, r_pol = p["semi_major_axis"], p["semi_minor_axis"]
    lon0 = np.deg2rad(p["longitude_of_projection_origin"])
    x, y = np.meshgrid(ds["x"].values, ds["y"].values)
    a = np.sin(x) ** 2 + np.cos(x) ** 2 * (np.cos(y) ** 2 + (r_eq / r_pol) ** 2 * np.sin(y) ** 2)
    b = -2 * H * np.cos(x) * np.cos(y)
    c = H ** 2 - r_eq ** 2
    with np.errstate(invalid="ignore"):
        rs = (-b - np.sqrt(b ** 2 - 4 * a * c)) / (2 * a)
        sx = rs * np.cos(x) * np.cos(y)
        sy = -rs * np.sin(x)
        sz = rs * np.cos(x) * np.sin(y)
        lat = np.degrees(np.arctan((r_eq / r_pol) ** 2 * sz / np.sqrt((H - sx) ** 2 + sy ** 2)))
        lon = np.degrees(lon0 - np.arctan(sy / (H - sx)))
    return lat, lon


def indices_ventana(ds, dominio):
    lat, lon = latlon_goes(ds)
    lo0, lo1, la0, la1 = dominio
    m = (lon >= lo0) & (lon <= lo1) & (lat >= la0) & (lat <= la1)
    iy, ix = np.where(m)
    return slice(iy.min(), iy.max() + 1), slice(ix.min(), ix.max() + 1), lat, lon


def main():
    import argparse
    ap = argparse.ArgumentParser()
    C.agregar_args_periodo(ap)
    ap.add_argument("--todas-las-horas", action="store_true",
                    help="descarga las 24 h (por defecto solo HORAS_DESCARGA_UTC)")
    args = ap.parse_args()
    C.aplicar_periodo(args)
    horas = pd.date_range(C.FECHA_INICIO, pd.Timestamp(C.FECHA_FIN) + pd.Timedelta("23h"),
                          freq=f"{C.PASO_HORAS}h")
    if C.HORAS_DESCARGA_UTC is not None and not args.todas_las_horas:
        horas = horas[horas.hour.isin(C.HORAS_DESCARGA_UTC)]
    descargar(horas)


_FS = None
_VENTANA = None


def _iniciar_proceso(ventana):
    """Cada proceso tiene su propia conexion S3 (HDF5 no es seguro entre hilos)."""
    global _FS, _VENTANA
    _FS = s3fs.S3FileSystem(anon=True, skip_instance_cache=True)
    _VENTANA = ventana


def _bajar_en_proceso(t):
    return _bajar_una(_FS, t, _VENTANA)


def _bajar_una(fs, t, ventana):
    """Descarga y guarda una hora. Devuelve un mensaje."""
    salida = os.path.join(C.DATA_DIR, f"sst_{t:%Y%m%d_%H}.nc")
    prefijo = f"noaa-{C.SATELITE}/{C.PRODUCTO}/{t:%Y}/{t:%j}/{t:%H}/"
    try:
        archivos = sorted(fs.ls(prefijo))
    except FileNotFoundError:
        archivos = []
    if not archivos:
        return f"[sin archivo] {t}"
    sy, sx, lat_w, lon_w, firma = ventana
    try:
        with fs.open(archivos[0], "rb") as f:
            ds = xr.open_dataset(f, engine="h5netcdf")
            if _firma(ds, sy, sx) != firma:
                # la grilla cambio (p. ej. reubicacion del satelite): el recorte quedaria
                # desplazado, asi que el archivo se descarta
                return f"[grilla distinta, descartado] {t}: {_firma(ds, sy, sx)} != {firma}"
            sub = ds[["SST", "DQF"]].isel(y=sy, x=sx).load()
    except Exception as e:  # archivo corrupto o corte de red: se reintenta en la proxima corrida
        return f"[error] {t}: {e}"
    sst = sub["SST"].where(np.isin(sub["DQF"], C.DQF_VALIDOS)) - 273.15
    out = xr.Dataset(
        {"sst": (("y", "x"), sst.values.astype("float32"), {"units": "degC"}),
         "dqf": (("y", "x"), sub["DQF"].values.astype("int8"))},
        coords={"lat": (("y", "x"), lat_w.astype("float32")),
                "lon": (("y", "x"), lon_w.astype("float32")),
                "time": t},
        attrs={"fuente": archivos[0], "producto": C.PRODUCTO},
    )
    out.to_netcdf(salida + ".tmp")
    os.replace(salida + ".tmp", salida)
    return f"[ok] {t}  validos={np.isfinite(sst.values).mean():.0%}"


def _firma(ds, sy, sx):
    """Identifica la grilla: longitud del origen y coordenadas de la esquina del recorte."""
    lon0 = float(ds["goes_imager_projection"].attrs["longitude_of_projection_origin"])
    return (round(lon0, 3), ds.sizes["x"], ds.sizes["y"],
            round(float(ds["x"][sx.start]), 7), round(float(ds["y"][sy.start]), 7))


def _ventana(fs, horas):
    """Indices del recorte, calculados con el primer archivo disponible."""
    for t in horas:
        prefijo = f"noaa-{C.SATELITE}/{C.PRODUCTO}/{t:%Y}/{t:%j}/{t:%H}/"
        try:
            archivos = sorted(fs.ls(prefijo))
        except FileNotFoundError:
            continue
        if archivos:
            with fs.open(archivos[0], "rb") as f:
                ds = xr.open_dataset(f, engine="h5netcdf")
                sy, sx, lat, lon = indices_ventana(ds, C.DOMINIO)
                firma = _firma(ds, sy, sx)
            print(f"Grilla de referencia: {firma}")
            return sy, sx, lat[sy, sx], lon[sy, sx], firma
    return None


def descargar(horas):
    """Descarga y recorta las horas dadas (DatetimeIndex UTC); salta las ya bajadas."""
    from concurrent.futures import ProcessPoolExecutor, as_completed
    os.makedirs(C.DATA_DIR, exist_ok=True)
    pendientes = [t for t in horas
                  if not os.path.exists(os.path.join(C.DATA_DIR, f"sst_{t:%Y%m%d_%H}.nc"))]
    print(f"{len(horas)} horas en el periodo, {len(pendientes)} por descargar")
    if not pendientes:
        return
    fs = s3fs.S3FileSystem(anon=True)
    ventana = _ventana(fs, pendientes)
    if ventana is None:
        print("No se encontraron archivos en el bucket para estas horas")
        return
    with ProcessPoolExecutor(C.DESCARGAS_PARALELAS, initializer=_iniciar_proceso,
                             initargs=(ventana,)) as ex:
        futuros = [ex.submit(_bajar_en_proceso, t) for t in pendientes]
        distintas = 0
        for i, fut in enumerate(as_completed(futuros), 1):
            msg = fut.result()
            distintas += msg.startswith("[grilla distinta")
            print(f"{i}/{len(pendientes)} {msg}", flush=True)
    if distintas:
        print(f"AVISO: {distintas} archivos con una grilla distinta se descartaron.")


if __name__ == "__main__":
    main()
