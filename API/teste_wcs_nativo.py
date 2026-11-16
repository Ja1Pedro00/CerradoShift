
import asyncio
import io

import httpx
import numpy as np
import rasterio
from pyproj import Transformer

LAT = -18.92
LON = -48.28

CRS_NATIVE = (
    "http://www.opengis.net/def/crs/EPSG/0/152160"
)

PROJ_NATIVE = "+proj=igh +datum=WGS84 +no_defs"


async def main():
    transformer = Transformer.from_crs(
        "EPSG:4326",
        PROJ_NATIVE,
        always_xy=True,
    )

    x, y = transformer.transform(LON, LAT)

    print("Coordenadas WGS84:", LON, LAT)
    print("Coordenadas Homolosine:", x, y)

    # Janela de 1500 x 1500 metros.
    margem = 750

    params = [
        ("map", "/map/clay.map"),
        ("SERVICE", "WCS"),
        ("VERSION", "2.0.1"),
        ("REQUEST", "GetCoverage"),
        ("COVERAGEID", "clay_0-5cm_mean"),
        ("FORMAT", "GEOTIFF_INT16"),
        ("SUBSETTINGCRS", CRS_NATIVE),
        ("OUTPUTCRS", CRS_NATIVE),
        ("SUBSET", f"X({x-margem},{x+margem})"),
        ("SUBSET", f"Y({y-margem},{y+margem})"),
    ]

    async with httpx.AsyncClient(
        timeout=45,
        follow_redirects=True,
    ) as client:
        response = await client.get(
            "https://maps.isric.org/mapserv",
            params=params,
        )

        print("HTTP:", response.status_code)
        print(
            "Content-Type:",
            response.headers.get("content-type"),
        )

        response.raise_for_status()

    content = response.content

    if content[:4] not in (
        b"II*\x00",
        b"MM\x00*",
    ):
        print("Resposta não é GeoTIFF:")
        print(content[:1000].decode(
            "utf-8", errors="replace"
        ))
        return

    with rasterio.MemoryFile(content) as mem:
        with mem.open() as ds:
            array = ds.read(1, masked=True)
            validos = array.compressed()

            print("\n=== RASTER NATIVO ===")
            print("CRS:", ds.crs)
            print("Bounds:", ds.bounds)
            print("NoData:", ds.nodata)
            print("Dimensões:", ds.width, ds.height)
            print("Pixels válidos:", validos.size)

            if validos.size:
                print("Mínimo:", validos.min())
                print("Máximo:", validos.max())
                print(
                    "Pixels não zero:",
                    np.count_nonzero(validos),
                )

            # Para o diagnóstico, verifica o centro
            # da matriz, sem depender da interpretação
            # do código EPSG não convencional.
            r = ds.height // 2
            c = ds.width // 2

            print("Pixel central:", array[r, c])

            print("\nMatriz recebida:")
            print(array)

            # Apenas referência de conversão:
            # argila SoilGrids: valor bruto / 10.
            if validos.size and np.count_nonzero(validos):
                print(
                    "\nExistem valores não zero.",
                    "A extração poderá ser ajustada."
                )
            else:
                print(
                    "\nRaster continua zerado.",
                    "Investigar cobertura/serviço."
                )


if __name__ == "__main__":
    asyncio.run(main())
