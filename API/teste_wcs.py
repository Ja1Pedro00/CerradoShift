
import asyncio
import httpx

from providers.soil_wcs import _fetch_one


async def main():
    async with httpx.AsyncClient(
        timeout=30
    ) as client:

        prop, depth, raw, error = await _fetch_one(
            client=client,
            lat=-18.92,
            lon=-48.28,
            prop="clay",
            depth="0-5cm",
            half_span_deg=0.007,
        )

        print("\nRESULTADO FINAL")
        print("Propriedade:", prop)
        print("Profundidade:", depth)
        print("Valor bruto:", raw)
        print("Erro:", error)

        if raw is not None:
            print("Argila estimada (%):", raw / 10)


if __name__ == "__main__":
    asyncio.run(main())
