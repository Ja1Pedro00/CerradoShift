# CerradoShift — frontend novo + API e motor matemático integrados

Este pacote mantém a API original de contexto ambiental, substitui apenas a aplicação frontend pelo novo projeto visual e incorpora o motor matemático do pacote `CerradoShift_MVP_Cerrado_v0.5` dentro da mesma API.

## O que foi preservado e conectado

- A API original continua em `API/app.py`, com seus provedores, cache, contratos `/v1/*` e integrações NASA/solo/clima/satélite.
- O frontend foi substituído pelo novo projeto React/Vite enviado em `CerradoShift.zip`.
- O serviço de comunicação do frontend usa `VITE_API_BASE_URL` e os contratos reais da API; as rotas antigas inexistentes `/api/clima`, `/api/solo` e `/api/comparar` não são mais utilizadas.
- O motor científico foi copiado para `API/formula_engine` (namespace separado para não conflitar com `API/app.py`) e suas rotas `/api/v1/*` são montadas no processo FastAPI existente.
- A Calculadora executa os endpoints dual Kc e resposta relativa de rendimento à água.
- Análises e Cenários executa a avaliação de sequência hospedeiro–praga e consulta contexto ambiental para os talhões selecionados.
- Os dados de talhões e estratégias continuam no `localStorage`, conforme a implementação do novo frontend.

## Como executar

### 1. API

No diretório `API/`:

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

A documentação interativa fica em `http://127.0.0.1:8000/docs`.

### 2. Frontend

No diretório `Frontend/`, copie `.env.example` para `.env`:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

Depois execute:

```bash
npm ci
npm run dev
```

Requisito: Node.js 22.22.0 ou superior (versão exigida pelo React Router do frontend novo).

## Motor matemático disponível localmente

Não é necessário subir um segundo servidor de fórmulas nem configurar `FORMULAS_BASE_URL` para usar o motor novo. As rotas estão sob `/api/v1`:

- `GET /api/v1/crop-catalog`
- `GET /api/v1/cerrado-mvp/catalog`
- `POST /api/v1/assessments/field`
- `POST /api/v1/assessments/vegetation-indices`
- `POST /api/v1/assessments/vegetation-anomaly`
- `POST /api/v1/assessments/erosion`
- `POST /api/v1/assessments/rotation`
- `POST /api/v1/assessments/phenology-thermal`
- `POST /api/v1/assessments/dual-kc`
- `POST /api/v1/assessments/yield-water-response`
- `POST /api/v1/assessments/cerrado-transition-options`
- `POST /api/v1/assessments/recommendations`

As rotas legadas `/v1/rotation-options` agora usam o motor local. A rota `/v1/plan` retorna o contexto ambiental real e informa quando ainda faltam parâmetros agronômicos para executar um cálculo; nenhum resultado é inventado. O novo frontend usa os endpoints locais `/api/v1`.

## Limites científicos a preservar

- NDVI/EVI e demais índices precisam de reflectância de superfície preparada e máscara de qualidade; as fórmulas não baixam cenas automaticamente.
- Anomalia espectral precisa de média e desvio-padrão históricos comparáveis.
- RUSLE depende de fatores R/K/LS/C/P compatíveis e calibrados localmente.
- GDD depende de clima e limites específicos da cultura/cultivar/fase.
- Ky, Kc, Kcb, Ks, parâmetros de solo e fenologia devem ser informados ou validados para a cultura e região.
- Os módulos são ferramentas de cálculo/triagem; não geram prescrição agronômica, dose de insumo nem produtividade absoluta.

A documentação original das fórmulas, do motor de recomendações e do MVP está em `API/formula_engine/docs/`. Exemplos de payloads estão em `API/formula_engine/examples/`.

## Verificações executadas

- Importação da API integrada e montagem das rotas locais `/api/v1`: OK.
- `GET /api/v1/health`: HTTP 200.
- `POST /api/v1/assessments/dual-kc`: HTTP 200 e retorno numérico conferido.
- `POST /api/v1/assessments/yield-water-response`: HTTP 200 e retorno numérico conferido.
- `POST /api/v1/assessments/rotation`: HTTP 200 e transições retornadas.
- Suíte de testes da API e motor matemático: 54 testes passaram.
- Build Vite/Oxlint não foi concluído neste ambiente: o ZIP original trazia dependências nativas para Windows e o pacote nativo Linux não estava disponível no cache offline. `node_modules` foi excluído do pacote final; execute `npm ci` no computador de desenvolvimento para instalar as dependências corretas da plataforma e então rode `npm run build`.

## Deploy

Defina `VITE_API_BASE_URL` com a URL pública real da API antes de compilar o frontend. Configure `CORS_ORIGINS` na API para aceitar o domínio do frontend. O valor padrão localhost serve apenas para desenvolvimento local.


## Dashboard conectado à API

O Dashboard consulta `POST /v1/field-context` para o talhão selecionado em `cerradoshift_talhoes`.
Temperatura média, precipitação acumulada e radiação solar média vêm do NASA POWER;
umidade do solo vem do NASA POWER (zona radicular) ou Open-Meteo (camada 7–28 cm).
Quando uma fonte não retorna um valor numérico, o cartão informa que não há dado disponível
em vez de exibir números demonstrativos. O usuário pode escolher qual talhão analisar.

## Aba Configurações do produtor

A rota `/configuracoes` agora contém o formulário de perfil da propriedade e do talhão. Consulte `Frontend/CONFIGURACOES_PRODUTOR.md` para os campos, armazenamento, payloads e roteiro de testes. As preferências e perfis são salvos localmente no navegador (`localStorage`) e podem ser exportados/importados como JSON; a importação associa o perfil exportado ao talhão selecionado no dispositivo de destino. Ainda não há persistência multiusuário no servidor.
