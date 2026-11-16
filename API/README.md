# CerradoShift — API de Contexto (solo, água, clima e satélite)

API que transforma **dados abertos de solo, clima, água e satélite** em um
payload único e previsível e também publica o motor matemático CerradoShift v0.5
no mesmo processo FastAPI.

```
App do agricultor  ──►  ESTA API  ──►  Motor matemático local
                     (agrega + normaliza + cacheia + calcula)
```

A API agrega os dados ambientais e disponibiliza o motor científico em
`formula_engine/`, com endpoints sob `/api/v1/assessments/*`. As rotas legadas
`/v1/plan` e `/v1/rotation-options` ainda aceitam encaminhamento externo opcional
via `FORMULAS_BASE_URL`, mas o novo frontend usa diretamente o motor local.

**Escopo do MVP:** Brasil (Cerrado), culturas comerciais **soja, milho e
algodão** + culturas de transição (**milheto, *Urochloa ruziziensis*,
*Crotalaria spectabilis*, *Crotalaria ochroleuca***). A arquitetura já aceita
novas culturas.

---

## 1. Como rodar

```powershell
cd "$env:USERPROFILE\Desktop\api"
.\run.ps1            # http://127.0.0.1:8000/docs
```

Na primeira execução o `run.ps1` cria o `.venv`, instala as dependências e
copia `.env.example` para `.env`.

Manual:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app:app --port 8000 --reload
```

Nenhuma chave é necessária para subir. Cache local em `.cache/` (JSON por
URL + parâmetros, com TTL), o que deixa a segunda chamada do mesmo talhão em
~70 ms. A série de NDVI tem cache próprio de 6 h em `.cache/vegetation/`.

> **Windows + usuário com acento no nome:** o GDAL falha ao ler o
> `cacert.pem` de um caminho com `Â`/`ó`. O `providers/geo.py` copia o
> certificado para um caminho ASCII e aponta `CURL_CA_BUNDLE` / `SSL_CERT_FILE`
> **antes** de importar o `rasterio`. Não remova esse bloco.

---

## 2. Estado real das fontes (testado a partir desta máquina em 14/11/2026)

| Fonte | Acesso | Já plugado | Para quê |
|---|---|---|---|
| **NASA POWER** | aberto | ✅ | chuva, Tmax/Tmin, ET, radiação e umidade do solo (MERRA-2) |
| **HLS v2 (Harmonized Landsat-Sentinel)** | aberto (via Planetary Computer) | ✅ | **NDVI e EVI por polígono do talhão** (30 m, ~2–3 dias) |
| **USDA Soil Data Access (SSURGO)** | aberto | ✅ | textura, matéria orgânica, AWC, drenagem, grupo hidrológico, declive (EUA) |
| **Open-Meteo** (ERA5-Land) | aberto | ✅ | ET0 FAO-56, previsão de 14 dias, umidade volumétrica do solo |
| **STAC Planetary Computer** | aberto | ✅ | disponibilidade de Sentinel-2 (10 m) e Landsat (30 m) |
| **USGS Water Data (NWIS)** | aberto | ✅ | estações de monitoramento num raio de ~25 km (EUA) |
| **ISRIC SoilGrids** | aberto | ⚠️ | solo global 250 m — API instável (às vezes devolve nulo) |
| **SMAP L4** | Earthdata Login | ❌ | umidade do solo a cada 2–3 dias (proxy atual: GWETROOT do POWER) |
| **GPM / IMERG** | Earthdata Login | ❌ | precipitação por satélite e eventos extremos |
| **ECOSTRESS** | Earthdata Login | ❌ | LST e ET em alta resolução |
| **GEDI** | Earthdata Login | ❌ | biomassa/dossel no entorno |
| **AppEEARS** | Earthdata Login | ❌ | série temporal de pontos (MODIS/VIIRS/SMAP) |
| **NASS QuickStats** | chave gratuita | ❌ | rendimento e área plantada (EUA) |
| **AMS Market News** | chave gratuita | ❌ | preço e demanda de commodities (EUA) |
| **OpenET** | chave gratuita | ❌ | ET de verdade em escala de campo (oeste dos EUA) |
| **Copernicus Data Space** | OAuth | ❌ | Sentinel-2 (catálogo aberto, download com token) |
| **ERA5 / CDS** | chave | ❌ | reanálise horária (já coberto via Open-Meteo) |

`GET /v1/sources` devolve essa matriz em JSON, com endpoint e credencial de cada
fonte — útil para a apresentação e para não perdermos tempo com o que não dá.

**Conta Earthdata (gratuita):** https://urs.earthdata.nasa.gov/users/new — libera
SMAP, GPM/IMERG, ECOSTRESS, GEDI e AppEEARS.

**Bloqueio de rede local:** `mrlc.gov` e `landfire.gov` recusam conexão daqui
(ECONNREFUSED, provavelmente bloqueio do provedor). O equivalente (NLCD,
LANDFIRE) pode ser obtido por STAC/ArcGIS — não é bloqueio da API.

### Cobertura geográfica

SSURGO, PRISM, NAIP, NLCD, NASS, OpenET e NWIS são **só EUA**. Como a demo é no
**Brasil**, o solo automático vem do **SoilGrids** (global, 250 m) e, quando o
produtor envia um laudo (`soil_override`), **o laudo manda**. Clima, ET0,
previsão, Sentinel-2 e HLS são globais.

Todo valor de solo carrega um rótulo de origem em `soil.origins`:

```json
"origins": {
  "clay_pct": "medido/informado pelo produtor",
  "sand_pct": "ISRIC SoilGrids 2.0",
  "awc_mm_rootzone": "calculado (FC − PWP) × profundidade efetiva"
}
```

---

## 3. Endpoints

### `POST /v1/field-context`

Aceita **polígono** (`geometry`, preferido) ou **lat/lon**. Com polígono, a API
calcula o centroide para clima/solo e usa o polígono inteiro nas consultas STAC,
além de estimar a área em hectares quando `area_ha` não é enviada.

#### `target_crop` — “qual plantio deseja efetuar?”

É o campo que responde ao fluxo do app: o agricultor escolhe **o que quer
plantar** e a API devolve as condições daquele lugar. Aceita português ou inglês
e normaliza para o nome usado pelas fórmulas:

| O app manda | A API normaliza para |
|---|---|
| `soja`, `soy`, `soybean` | `soybean` |
| `milho`, `maize`, `corn` | `corn` |
| `algodão`, `algodao`, `cotton` | `cotton` |
| `milheto`, `millet` | `millet` |
| `braquiária`, `ruziziensis` | `urochloa_ruziziensis` |
| `crotalária spectabilis` | `crotalaria_spectabilis` |
| `crotalária ochroleuca` | `crotalaria_ochroleuca` |

A resposta devolve `location.target_crop` (normalizado), `target_crop_raw` (como
o app mandou), `target_crop_known` (se está no catálogo MVP) e
`target_crop_source` (`target_crop`, `rotation_candidates[0]` ou `current_crop`).
Nome desconhecido **não é bloqueado** — apenas gera um alerta `unknown_target_crop`.

> **Limite importante:** solo, chuva, ET₀ e NDVI **não mudam** com a cultura —
> eles são propriedades do lugar. O que muda com a cultura é a **interpretação**
> (“milho precisa de mais água que algodão nesta fase?”), e isso é decidido pelo
> CerradoShift (`/v1/plan`), que recebe `target_crop` junto com o contexto.

```json
{
  "geometry": {
    "type": "Polygon",
    "coordinates": [[
      [-47.930, -15.780], [-47.920, -15.780],
      [-47.920, -15.790], [-47.930, -15.790],
      [-47.930, -15.780]
    ]]
  },
  "field_id": "talhao-01",
  "planting_date": "2026-11-20",
  "target_crop": "corn",
  "current_crop": "soybean",
  "rotation_candidates": ["corn", "cotton", "crotalaria"],
  "irrigation": "rainfed",
  "window_days": 365,
  "forecast_days": 14,
  "soil_override": {
    "clay_pct": 35, "sand_pct": 50, "silt_pct": 15,
    "ph_h2o": 5.8, "phosphorus_mg_dm3": 12, "potassium_mg_dm3": 80,
    "field_capacity_m3m3": 0.32, "wilting_point_m3m3": 0.18,
    "root_depth_cm": 100
  }
}
```

Resposta (resumida):

```json
{
  "request_id": "…",
  "location": {
    "lat": -15.785, "lon": -47.925,
    "geometry": { "type": "Polygon", "coordinates": [[…]] },
    "area_ha": 1.24,
    "target_crop": "corn",
    "target_crop_raw": "milho",
    "target_crop_known": true,
    "target_crop_source": "target_crop",
    "rotation_candidates": ["corn", "cotton", "crotalaria"]
  },
  "window": { "start": "2025-11-14", "end": "2026-11-13", "days": 365 },
  "climate": {
    "precip_mm_total": 1090.3,
    "et_mm_total": 850.34,
    "et0_mm_total": 1018.26,
    "net_water_balance_mm": 240.0,
    "longest_dry_spell_days": 70,
    "soil_moisture_rootzone": { "mean": 0.61, "trend": "caindo" },
    "forecast": { "precip_mm_total": 200.9, "et0_mm_total": 81.32 }
  },
  "soil": {
    "provider": "ISRIC SoilGrids 2.0 + ajuste do agricultor",
    "texture_class": "franco-argilo-arenosa",
    "clay_pct": 35.0, "sand_pct": 50.0, "silt_pct": 15.0,
    "field_capacity_m3m3": 0.32, "wilting_point_m3m3": 0.18,
    "awc_mm_rootzone": 140.0,
    "origins": { "clay_pct": "medido/informado pelo produtor" }
  },
  "water": { "monitoring_locations_nearby": 0 },
  "vegetation": { "scenes_found": 12, "recent_clear_scenes_60d": 2 },
  "indicators": {
    "aridity_index_unep": 0.576,
    "climate_class": "subúmido seco",
    "drought_risk": "moderado",
    "drought_risk_basis": ["maior veranico de 70 dias"],
    "data_completeness": 1.0
  },
  "alerts": [
    {
      "severity": "atencao",
      "code": "low_awc",
      "title": "Baixa reserva de água no solo (49 mm)",
      "detail": "O solo armazena pouca água disponível para as raízes.",
      "action": "Cobertura do solo (palhada) e irrigação reduzem o risco em veranicos.",
      "basis": ["soil.awc_mm_rootzone"]
    }
  ],
  "alerts_summary": { "critico": 0, "atencao": 3, "info": 2 },
  "warnings": [],
  "sources": [ { "name": "NASA POWER", "status": "ok", "cached": true } ]
}
```

Sempre devolve `sources` e `warnings`: em demo, se uma fonte cair, a resposta
continua de pé e a tela consegue explicar o que faltou.

#### `alerts` — triagem automática, não laudo

Cada alerta traduz **um dado real** em uma prevenção, sempre apontando o campo
de origem em `basis` (ex.: `soil.ph_h2o`). Severidades:

| `severity` | Leitura |
|---|---|
| `critico` | Condição que pode inviabilizar a safra se ignorada (ex.: risco de seca alto, declive > 10%, salinidade). |
| `atencao` | Precisa de manejo/checagem (pH ácido, solo arenoso, matéria orgânica baixa, veranico). |
| `info` | Transparência sobre o dado (solo veio de pixel vizinho, laudo aplicado, sem estação fluviométrica). |

Regras implementadas hoje: risco de seca (alto/moderado), geada, calor extremo,
previsão de chuva intensa ou seca, pH ácido/alcalino, matéria orgânica baixa,
AWC baixa, solo muito argiloso/arenoso, drenagem deficiente, declive, salinidade,
P e K baixos (quando vêm do laudo), ausência de estação fluviométrica, sem cena
de satélite limpa, ausência de solo automático, solo de pixel vizinho e laudo
aplicado.

> **Importante para a apresentação:** `alerts` é **triagem baseada em dados**,
> não recomendação agronômica e não substitui análise de laboratório. Quem
> decide “pode plantar?” é o CerradoShift (`/v1/plan`).

### `POST /v1/vegetation-series`

**NDVI/EVI por talhão** usando HLS v2 (`hls2-s30` + `hls2-l30`) via STAC do
Planetary Computer. A API assina as cenas (SAS token), abre **somente a janela
do polígono** dentro do COG (não baixa a cena inteira) e mascara nuvem/sombra
pelo `Fmask`. ~7–8 s por cena, buscadas em paralelo; cache de 6 h.

```json
{
  "geometry": { "type": "Polygon", "coordinates": [[ … ]] },
  "start": "2026-06-01",
  "end": "2026-11-14",
  "max_scenes": 8,
  "include_evi": true
}
```

Resposta:

```json
{
  "request_id": "…",
  "area_ha": 1.24,
  "source": "HLS v2 (Harmonized Landsat-Sentinel) via Planetary Computer STAC",
  "resolution_m": "30 (HLS)",
  "scenes_requested": 8,
  "scenes_processed": 6,
  "scenes": [
    { "date": "2026-07-02", "ndvi_mean": 0.81, "evi_mean": 0.62,
      "valid_pixel_pct": 97.3, "cloud_cover_pct": 12, "platform": "sentinel-2a" }
  ],
  "latest": { "date": "2026-11-02", "ndvi_mean": 0.34, "evi_mean": 0.21 },
  "trend": "caindo",
  "warning": "NDVI/EVI indicam vigor da vegetação, não diagnosticam a causa (praga, água ou nutriente).",
  "attribution": "HLS (NASA/USGS) — processado via Microsoft Planetary Computer"
}
```

> NDVI = (B05 − B04) / (B05 + B04); EVI usa B02/B04/B05 em reflectância
> (÷10000). Bits ruins do Fmask: `0b11110`.

### `POST /v1/rotation-options`

Encaminha a decisão de rotação para o **CerradoShift** no contrato exato deles
(`POST {FORMULAS_BASE_URL}{FORMULAS_TRANSITION_PATH}`):

```json
{
  "current_crop": "soybean",
  "next_crop": "cotton",
  "days_available": 75,
  "pratylenchus_brachyurus_status": "unknown",
  "objective": "balanced",
  "cotton_years_since_last": 3
}
```

Opcionalmente (`include_vegetation_series: true`) a API anexa a série de
NDVI/EVI do talhão ao retorno em `vegetation_series` — **sem** alterar o
contrato enviado ao CerradoShift.

A resposta tem `sent` (o que foi enviado), `options` (o que o CerradoShift
devolveu) e, se pedido, `vegetation_series`.

### `POST /v1/plan`

Monta o contexto e encaminha para `{FORMULAS_BASE_URL}{FORMULAS_FIELD_PATH}`
(padrão `/api/v1/assessments/field`). Sem `FORMULAS_BASE_URL`, responde **501**
com instrução de correção.

Contrato enviado:

```json
{ "request": { /* payload cru do app */ }, "context": { /* saída de /v1/field-context */ } }
```

### `GET /health`, `GET /v1/sources`, `GET /docs`

---

## 4. Contrato com o CerradoShift

Endpoints do time de fórmulas (CerradoShift 0.3.0):

| Método | Caminho | Uso |
|---|---|---|
| GET | `/api/v1/health` | saúde do serviço |
| GET | `/api/v1/cerrado-mvp/catalog` | catálogo de culturas |
| POST | `/api/v1/assessments/cerrado-transition-options` | opções de transição (`/v1/rotation-options`) |
| POST | `/api/v1/assessments/field` | avaliação de campo (`/v1/plan`) |

Configure no `.env`:

```ini
FORMULAS_BASE_URL=http://localhost:8000
FORMULAS_FIELD_PATH=/api/v1/assessments/field
FORMULAS_TRANSITION_PATH=/api/v1/assessments/cerrado-transition-options
```

Os indicadores (`indicators`) desta API são heurísticos e explicáveis — servem
para a tela e para conversa, **não** substituem as fórmulas.

---

## 5. Estrutura

```
api/
  app.py              rotas, agregação, indicadores, matriz de fontes
  config.py           .env / configuração (inclui URLs do CerradoShift)
  schemas.py          contratos de entrada e saída (OpenAPI)
  clients.py          HTTP + retry + cache em disco
  providers/
    power.py          NASA POWER
    geo.py            HLS NDVI/EVI por polígono (STAC + COG + Fmask)
    soil.py           USDA SDA + SoilGrids + laudo do produtor + origens
    meteo.py          Open-Meteo (ET0, previsão, umidade do solo)
    water.py          USGS NWIS
    vegetation.py     disponibilidade STAC Sentinel-2 / Landsat
  run.ps1             sobe a API no Windows
  requirements.txt
  .env.example
```

---

## 6. Próximos passos (ordem de impacto)

1. **Conta Earthdata** (https://urs.earthdata.nasa.gov/users/new) → SMAP real e
   AppEEARS para séries de ponto de MODIS/VIIRS.
2. **Validar os 3 primeiros talhões reais** com o time de fórmulas (NDVI vs.
   estágio da cultura).
3. **Plugar o CerradoShift** (`FORMULAS_BASE_URL`) e testar
   `/v1/rotation-options` de ponta a ponta.
4. **Catálogo ampliado** de culturas (sorgo, feijão, trigo, girassol) e
   perenes (café, cana) — a arquitetura já aceita.
5. **Chaves gratuitas**: NASS (rendimento histórico) e AMS (preço) — só depois
   do núcleo funcionar.
6. **Deploy**: container simples + cache em volume; CORS já configurável.


## Motor matemático incorporado

Os módulos de cálculo, esquemas, exemplos, testes e documentação do pacote v0.5 estão em `formula_engine/`, `tests/`, `formula_engine/examples/` e `formula_engine/docs/`. Consulte `README-INTEGRACAO.md` na raiz para a lista das rotas e a forma de execução conjunta.


## Atualização da integração local

A rota legada `POST /v1/rotation-options` executa agora o motor local `formula_engine.core.cerrado_mvp`, sem depender de `FORMULAS_BASE_URL`. A rota legada `POST /v1/plan` retorna o contexto ambiental e sinaliza que os parâmetros agronômicos completos ainda são necessários; os cálculos completos devem usar os endpoints `POST /api/v1/assessments/*`. O dashboard não apresenta números de demonstração: os indicadores ficam ocultos/aguardando até a API fornecer dados reais.
