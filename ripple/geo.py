"""Geography helpers and the fixed port table (real public names and coordinates)."""

from __future__ import annotations

import math

# UN/LOCODE -> (name, country, lat, lon)
PORTS: dict[str, tuple[str, str, float, float]] = {
    "CNSHA": ("Shanghai", "CN", 31.23, 121.49),
    "CNNGB": ("Ningbo-Zhoushan", "CN", 29.87, 121.55),
    "CNSZX": ("Shenzhen (Yantian)", "CN", 22.57, 114.27),
    "CNTAO": ("Qingdao", "CN", 36.07, 120.38),
    "HKHKG": ("Hong Kong", "HK", 22.29, 114.16),
    "SGSIN": ("Singapore", "SG", 1.26, 103.84),
    "KRPUS": ("Busan", "KR", 35.10, 129.04),
    "TWKHH": ("Kaohsiung", "TW", 22.61, 120.28),
    "VNSGN": ("Ho Chi Minh City", "VN", 10.77, 106.70),
    "MYPKG": ("Port Klang", "MY", 3.00, 101.39),
    "INNSA": ("Nhava Sheva (JNPT)", "IN", 18.95, 72.95),
    "AEJEA": ("Jebel Ali", "AE", 25.01, 55.06),
    "NLRTM": ("Rotterdam", "NL", 51.95, 4.14),
    "BEANR": ("Antwerp", "BE", 51.26, 4.40),
    "DEHAM": ("Hamburg", "DE", 53.54, 9.97),
    "ESVLC": ("Valencia", "ES", 39.45, -0.32),
    "GBFXT": ("Felixstowe", "GB", 51.96, 1.35),
    "USLAX": ("Los Angeles", "US", 33.73, -118.26),
    "USLGB": ("Long Beach", "US", 33.75, -118.21),
    "USNYC": ("New York/New Jersey", "US", 40.67, -74.04),
    "USSAV": ("Savannah", "US", 32.08, -81.09),
    "BRSSZ": ("Santos", "BR", -23.96, -46.30),
    "MXZLO": ("Manzanillo", "MX", 19.05, -104.32),
    "PAONX": ("Colón", "PA", 9.36, -79.90),
    "ZADUR": ("Durban", "ZA", -29.87, 31.03),
    "AUSYD": ("Sydney (Port Botany)", "AU", -33.97, 151.21),
}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))
