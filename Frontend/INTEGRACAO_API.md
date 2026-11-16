# Integração CerradoShift Frontend + API

## O que foi conectado

- `GET /health`: verificação de conectividade da API no Dashboard.
- `POST /v1/field-context`: consulta de clima, solo, água, vegetação, indicadores preliminares, alertas e status das fontes para um talhão GeoJSON.
- `POST /v1/vegetation-series`: consulta de série NDVI/EVI HLS para os polígonos selecionados na tela Análises e Cenários.
- `POST /v1/plan`: botão de teste do motor matemático. Enquanto `FORMULAS_BASE_URL` não estiver configurado no backend, a resposta esperada é HTTP 501.
- O endpoint `/v1/rotation-options` está disponível no cliente `src/services/api.js`, mas a tela não o chama automaticamente: seu contrato exige `days_available` e o serviço matemático remoto, então não devemos inventar esse valor ou exibir recomendação sem a equipe de fórmulas.

## Configuração local

1. Inicie a API FastAPI na porta 8000 (ou na porta escolhida).
2. Copie `.env.example` para `.env` neste projeto frontend.
3. Configure `VITE_API_BASE_URL=http://127.0.0.1:8000`.
4. Instale dependências com `npm install` (ou `npm ci`).
5. Inicie o frontend com `npm run dev`.

O Vite lê variáveis `VITE_` na inicialização; reinicie o servidor frontend depois de alterar `.env`.

## Configuração em produção

Defina `VITE_API_BASE_URL` no ambiente de build/deploy para a URL pública da API. A URL do frontend não é a URL da API. A API também precisa permitir a origem do frontend em `CORS_ORIGINS` (o código atual usa `*` por padrão, mas em produção é melhor restringir à origem do app).

## Como testar

1. Abra Mapa da Propriedade e desenhe um polígono fechado.
2. Clique em Selecionar no talhão recém-criado e em Consultar dados na API.
3. Confira os dados de clima/solo, as fontes com status `ok`/`error`, alertas e avisos.
4. No Dashboard, selecione o mesmo talhão e clique em Consultar API.
5. Cadastre pelo menos duas estratégias para habilitar a consulta de contexto e NDVI/EVI na página Análises e Cenários.
6. Use Testar endpoint `/v1/plan` para confirmar que a API chega ao backend; HTTP 501 é esperado até a configuração do motor matemático.

## Limites mantidos intencionalmente

- Os talhões e estratégias continuam salvos em `localStorage`; não há persistência multiusuário no servidor.
- Os alertas da API são triagem baseada em dados e não substituem laudo ou recomendação agronômica.
- Não há cálculo de produtividade, melhor cultura, época ideal, estresse específico por cultura ou ranking de rotação enquanto as fórmulas não forem fornecidas e validadas.
- A resposta de contexto pode conter campos nulos ou fontes com erro, por cobertura geográfica, indisponibilidade do provedor ou ausência de dados para o polígono.


## Configurações do produtor

- A página `src/pages/SettingsPage.jsx` implementa a aba Configurações.
- O formulário segue os campos do `RecommendationRequest`: talhão/cultura, `field`, `soil_test`, `pests`, `crop_history`, `preferences` e `rotation`.
- Os perfis ficam no `localStorage` sob `cerradoshift_configuracoes_v1`, separados pelo ID do talhão. Isso é local ao navegador; para persistência multiusuário, será necessário banco de dados e autenticação.
- `src/services/settingsStorage.js` converte o formulário em payload para `POST /api/v1/assessments/recommendations` e acrescenta os parâmetros suportados em `fieldRequest()` para `POST /v1/field-context`.
- O histórico `crop_history` é enviado da safra mais antiga para a mais recente e agora é aceito pelo schema de recomendações. Ele amplia a sequência usada na triagem de relações hospedeiro–praga.
- O botão “Testar configuração na API” envia `model_results` vazio intencionalmente. É teste do contrato e das recomendações baseadas nos dados de cadastro, não substitui a execução dos modelos ambientais.

Consulte `CONFIGURACOES_PRODUTOR.md` para o passo a passo de uso e teste.
