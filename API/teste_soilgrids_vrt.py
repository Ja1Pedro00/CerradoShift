
import numpy as np
import rasterio

from rasterio.warp import transform
from rasterio.windows import Window

LAT = -18.92
LON = -48.28

URL = (
    "/vsicurl/https://files.isric.org/"
    "soilgrids/latest/data/clay/"
    "clay_0-5cm_mean.vrt"
)

with rasterio.Env(
    GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
    GDAL_HTTP_TIMEOUT="30",
    GDAL_HTTP_MAX_RETRY="3",
    CPL_DEBUG="ON",
    CPL_CURL_VERBOSE="YES",
):
    with rasterio.open(URL) as ds:

        xs, ys = transform(
            "EPSG:4326",
            ds.crs,
            [LON],
            [LAT],
        )

        from pyproj import Transformer

        transformer = Transformer.from_crs(
            "EPSG:4326",
            "+proj=igh +datum=WGS84 +no_defs",
            always_xy=True,
        )

        x_proj, y_proj = transformer.transform(LON, LAT)

        print("\n=== COMPARAÇÃO DE COORDENADAS ===")
        print("Rasterio X:", xs[0])
        print("Rasterio Y:", ys[0])
        print("PyProj X:", x_proj)
        print("PyProj Y:", y_proj)
        print("Diferença X:", abs(xs[0] - x_proj))
        print("Diferença Y:", abs(ys[0] - y_proj))
        print("Bounds:", ds.bounds)

        row, col = ds.index(xs[0], ys[0])

        print("CRS:", ds.crs)
        print("NoData:", ds.nodata)
        print("Posição:", row, col)

        # Leitura direta do pixel
        janela = Window(col, row, 1, 1)

        bruto = ds.read(
            1,
            window=janela,
            masked=False,
        )

        mascara = ds.read_masks(
            1,
            window=janela,
        )

        print("Valor bruto:", bruto[0, 0])
        print("Máscara GDAL:", mascara[0, 0])

        # Vizinhança 5x5
        janela_local = Window(
            col - 2,
            row - 2,
            5,
            5,
        )

        vizinhos = ds.read(
            1,
            window=janela_local,
            masked=True,
        )

        print("\nVizinhança 5x5:")
        print(vizinhos)

        print(
            "Pixels não mascarados:",
            vizinhos.count(),
        )

        print(
            "Pixels não zero válidos:",
            np.count_nonzero(
                vizinhos.compressed()
            ),
        )

        if mascara[0, 0] == 0:
            print(
                "\nPixel sem dado válido ou não "
                "carregado corretamente."
            )
        else:
            valor = float(bruto[0, 0])

            print(
                "\nArgila estimada (%):",
                valor / 10,
            )
