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
    horas = pd.date_range(C.FECHA_INICIO, pd.Timestamp(C.FECHA_FIN) + pd.Timedelta("23h"),
                          freq=f"{C.PASO_HORAS}h")
    if C.HORAS_DESCARGA_UTC is not None:
        horas = horas[horas.hour.isin(C.HORAS_DESCARGA_UTC)]
    print(f"{len(horas)} horas a descargar ({C.FECHA_INICIO} a {C.FECHA_FIN})")
    descargar(horas)


def descargar(horas):
    """Descarga y recorta las horas dadas (DatetimeIndex UTC); salta las ya bajadas."""
    fs = s3fs.S3FileSystem(anon=True)
    os.makedirs(C.DATA_DIR, exist_ok=True)
    ventana = None
    for t in horas:
        salida = os.path.join(C.DATA_DIR, f"sst_{t:%Y%m%d_%H}.nc")
        if os.path.exists(salida):
            continue
        prefijo = f"noaa-{C.SATELITE}/{C.PRODUCTO}/{t:%Y}/{t:%j}/{t:%H}/"
        try:
            archivos = sorted(fs.ls(prefijo))
        except FileNotFoundError:
            archivos = []
        if not archivos:
            print(f"[sin archivo] {t}")
            continue
        with fs.open(archivos[0], "rb") as f:
            ds = xr.open_dataset(f, engine="h5netcdf")
            if ventana is None:
                sy, sx, lat, lon = indices_ventana(ds, C.DOMINIO)
                ventana = (sy, sx, lat[sy, sx], lon[sy, sx])
            sy, sx, lat_w, lon_w = ventana
            sub = ds[["SST", "DQF"]].isel(y=sy, x=sx).load()
        sst = sub["SST"].where(np.isin(sub["DQF"], C.DQF_VALIDOS)) - 273.15
        out = xr.Dataset(
            {"sst": (("y", "x"), sst.values.astype("float32"), {"units": "degC"}),
             "dqf": (("y", "x"), sub["DQF"].values.astype("int8"))},
            coords={"lat": (("y", "x"), lat_w.astype("float32")),
                    "lon": (("y", "x"), lon_w.astype("float32")),
                    "time": t},
            attrs={"fuente": archivos[0], "producto": C.PRODUCTO},
        )
        out.to_netcdf(salida)
        print(f"[ok] {t}  validos={np.isfinite(sst.values).mean():.0%}")


if __name__ == "__main__":
    main()
