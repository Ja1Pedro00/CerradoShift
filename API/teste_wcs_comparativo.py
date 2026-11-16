
import asyncio

import httpx
import numpy as np
from pyproj import Transformer
from rasterio.io import MemoryFile

URL = "https://maps.isric.org/mapserv"

CRS = "http://www.opengis.net/def/crs/EPSG/0/152160"

TRANSFORMER = Transformer.from_crs(
    "EPSG:4326",
    "+proj=igh +datum=WGS84 +no_defs",
    always_xy=True,
)

LOCAIS = {
    "Uberlandia": (-18.92, -48.28),
    "Paris": (48.8566, 2.3522),
    "Brasilia": (-15.7939, -47.8828),
}


async def testar(client, nome, lat, lon):
    x, y = TRANSFORMER.transform(lon, lat)

    margem = 5000

    params = [
        ("map", "/map/clay.map"),
        ("SERVICE", "WCS"),
        ("VERSION", "2.0.1"),
        ("REQUEST", "GetCoverage"),
        ("COVERAGEID", "clay_0-5cm_mean"),
        ("FORMAT", "GEOTIFF_INT16"),
        ("SUBSETTINGCRS", CRS),
        ("OUTPUTCRS", CRS),
        ("SUBSET", f"X({x-margem},{x+margem})"),
        ("SUBSET", f"Y({y-margem},{y+margem})"),
    ]

    print(f"\n=== {nome} ===")

    try:
        response = await client.get(URL, params=params)
        response.raise_for_status()

        print("HTTP:", response.status_code)
        print(
            "Content-Type:",
            response.headers.get("content-type"),
        )

        if response.content[:4] not in (
            b"II*\x00",
            b"MM\x00*",
        ):
            print(response.text[:500])
            return

        with MemoryFile(response.content) as mem:
            with mem.open() as ds:
                raster = ds.read(1, masked=True)

                # Localiza pixels diferentes de zero
                matriz = np.ma.filled(raster, 0)

                linhas, colunas = np.where(
                    matriz != 0
                )

                if len(linhas) > 0:

                    distancias = []

                    for r, c in zip(linhas, colunas):
                        px, py = ds.xy(
                            int(r),
                            int(c),
                        )

                        distancia = (
                            (px - x) ** 2
                            + (py - y) ** 2
                        ) ** 0.5

                        distancias.append((
                            distancia,
                            int(r),
                            int(c),
                            float(matriz[r, c]),
                        ))

                    distancias.sort(
                        key=lambda item: item[0]
                    )

                    print(
                        "\n=== PIXELS NÃO ZERO MAIS PRÓXIMOS ==="
                    )

                    for distancia, r, c, valor in distancias[:5]:
                        print(
                            f"Posição: ({r}, {c}) | "
                            f"Distância: {distancia:.1f} m | "
                            f"Valor bruto: {valor}"
                        )

                else:
                    print(
                        "Nenhum pixel diferente de zero."
                    )

                validos = raster.compressed()


                print("Dimensoes:", ds.width, ds.height)
                print("NoData:", ds.nodata)
                print("Pixels validos:", validos.size)

                if validos.size:
                    print("Minimo:", validos.min())
                    print("Maximo:", validos.max())
                    print(
                        "Pixels nao zero:",
                        np.count_nonzero(validos),
                    )

                    r, c = ds.index(x, y)

                    if 0 <= r < ds.height and 0 <= c < ds.width:
                        print("Pixel do ponto:", raster[r, c])

    except Exception as exc:
        print("ERRO:", type(exc).__name__, str(exc))


async def main():
    async with httpx.AsyncClient(timeout=60) as client:
        for nome, (lat, lon) in LOCAIS.items():
            await testar(client, nome, lat, lon)


if __name__ == "__main__":
    asyncio.run(main())
