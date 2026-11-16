
import httpx
import xml.etree.ElementTree as ET

URL = (
    "https://files.isric.org/soilgrids/latest/data/"
    "clay/clay_0-5cm_mean.vrt"
)

response = httpx.get(
    URL,
    timeout=30,
    follow_redirects=True,
)

print("HTTP:", response.status_code)
print("Content-Type:", response.headers.get("content-type"))
print("Tamanho:", len(response.content), "bytes")

response.raise_for_status()

root = ET.fromstring(response.content)

sources = root.findall(".//SourceFilename")

print("Arquivos referenciados:", len(sources))

for source in sources[:10]:
    print(
        "Arquivo:",
        source.text,
        "| relativeToVRT:",
        source.attrib.get("relativeToVRT"),
    )