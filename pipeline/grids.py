"""Coordinate-system helpers shared by the reprojection step and its tests."""

from __future__ import annotations

import math

from rasterio.crs import CRS

MARS_RADIUS_M = 3_396_190.0
MOON_RADIUS_M = 1_737_400.0


def utm_crs(lat: float, lon: float) -> CRS:
    """WGS84 UTM zone CRS containing (lat, lon)."""
    zone = int(math.floor((lon + 180.0) / 6.0)) % 60 + 1
    epsg = (32600 if lat >= 0 else 32700) + zone
    return CRS.from_epsg(epsg)


def mars_aeqd_crs(lat0: float, lon0: float) -> CRS:
    """Azimuthal equidistant CRS on the Mars sphere, centred on (lat0, lon0).

    Distances from the centre are true, so slopes computed on this grid are not
    stretched east-west the way they are on the equirectangular source grid.
    """
    return CRS.from_proj4(
        f"+proj=aeqd +lat_0={lat0:.6f} +lon_0={lon0:.6f} +R={MARS_RADIUS_M:.0f} +units=m +no_defs"
    )


def mars_geographic_crs() -> CRS:
    """Geographic (lon/lat degrees) CRS on the Mars sphere."""
    return CRS.from_proj4(f"+proj=longlat +R={MARS_RADIUS_M:.0f} +no_defs")


def moon_geographic_crs() -> CRS:
    """Geographic (lon/lat degrees) CRS on the Moon sphere."""
    return CRS.from_proj4(f"+proj=longlat +R={MOON_RADIUS_M:.0f} +no_defs")


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float, radius_km: float = 6371.0088) -> float:
    """Great-circle distance in km between two points (degrees)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dlmb = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * radius_km * math.asin(min(1.0, math.sqrt(a)))
