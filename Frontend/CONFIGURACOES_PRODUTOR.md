# Aba Configurações do produtor — CerradoShift

## Para que serve

A página `/configuracoes` coleta as informações do talhão e as preferências do produtor usadas pelos modelos e pelo motor de recomendações. A implementação segue os contratos de `API/formula_engine/api/recommendation_schemas.py` e os requisitos de `API/formula_engine/docs/MVP_ESPECIFICACAO.md` e `MOTOR_RECOMENDACOES.md`.

## Seções disponíveis

1. **Propriedade e talhão:** nome opcional da propriedade e seleção de um talhão já desenhado em Mapa da Propriedade.
2. **Cultivo e planejamento de rotação:** cultura comercial atual, próxima cultura, fase observada, dias disponíveis, retorno do algodão e situação conhecida de *Pratylenchus brachyurus*.
3. **Histórico das últimas safras:** cultura comercial ou de transição, identificação da safra, datas de plantio e colheita. A ordem no formulário é da safra mais antiga para a mais recente. O histórico é enviado para `crop_history` na solicitação de recomendações.
4. **Água e estrutura:** área, declividade, sistema de irrigação, eficiência informada, limitação de água, orçamento e maquinário.
5. **Análise de solo:** data/laboratório, pH, método, interpretação do laboratório, situação de N/P/K/S/Ca/Mg, matéria orgânica, textura e compactação.
6. **Dados avançados de solo:** percentuais de argila/areia/silte, capacidade de campo, ponto de murcha, densidade, profundidade, AWC, pH e valores numéricos de nutrientes, drenagem e grupo hidrológico. Só preencher com laudo ou fonte técnica conhecida.
7. **Fitossanidade:** situação de *P. brachyurus* e outras observações com identificação, estado, severidade, data e notas.
8. **Preferências:** prioridades, objetivo principal, tolerância a risco, culturas de transição evitadas e observações.
9. **Integração:** teste de conectividade da API, consulta de estado das fontes e envio de uma solicitação de recomendação.

## Persistência

Nesta versão, a configuração é salva no `localStorage` do navegador, na chave `cerradoshift_configuracoes_v1`, separada por ID de talhão. As preferências gerais ficam no mesmo registro. Talhões permanecem na chave já existente `cerradoshift_talhoes`.

Não há autenticação nem banco de dados multiusuário. Para transferir a configuração a outro computador ou compartilhá-la com a equipe, selecione primeiro o talhão de destino no outro dispositivo e use **Importar JSON**. O arquivo exportado identifica explicitamente o perfil selecionado, e a importação o associa ao talhão que estiver selecionado no momento. As preferências gerais também são importadas. Não incluir dados pessoais sensíveis nesse arquivo. Isso é transferência manual de arquivo, não sincronização em tempo real.

## Integração com a API

- `POST /api/v1/assessments/recommendations`: recebe preferências, dados de campo, análise de solo, observações fitossanitárias, histórico de safras e contexto de rotação.
- `POST /v1/field-context`: `fieldRequest()` lê configurações salvas do talhão e acrescenta `target_crop`, `current_crop`, tipo geral de irrigação e `soil_override` quando esses dados foram informados.
- `GET /v1/sources` e `GET /health`: usados para mostrar estado da API e das fontes.

O botão **Testar configuração na API** envia os dados atuais do formulário. Ele usa `model_results: {}` intencionalmente: serve para validar o contrato e mostrar recomendações baseadas nos dados preenchidos e lacunas de informação, mas não representa uma avaliação ambiental completa. Os resultados reais dos endpoints de água, vegetação, erosão e calor ainda precisam ser executados e anexados ao pedido pelo fluxo de análise.

## Testes manuais

1. Desenhar um talhão em Mapa da Propriedade.
2. Abrir Configurações e selecionar o talhão.
3. Informar cultura atual soja, próxima cultura algodão, dias disponíveis e status de nematoide desconhecido.
4. Registrar uma safra anterior no histórico.
5. Escolher pelo menos uma prioridade e salvar.
6. Atualizar a página e confirmar que os campos continuam preenchidos.
7. Clicar em Exportar JSON; depois importar o arquivo e verificar a mensagem de sucesso.
8. Com a API ligada, verificar a lista de fontes: “Integrada no backend” significa que o projeto tem um conector implementado; “integração pendente” significa que ainda não está conectada. A disponibilidade de uma fonte externa pode variar no momento da consulta.
9. Clicar em Testar configuração na API. Deve aparecer a lista retornada pelo backend e eventuais lacunas de dados.
10. Abrir Dashboard ou Diagnóstico do Solo para conferir que as configurações salvas de cultura/irrigação/solo acompanham a consulta do talhão quando os campos correspondentes são suportados pelo endpoint.

## Limitações conhecidas

- O armazenamento é local ao navegador/dispositivo; a equipe não recebe alterações automaticamente.
- Não há sincronização por usuário/conta nem salvamento em banco de dados.
- A tela não inventa parâmetros faltantes; pH, nutrientes e propriedades hidráulicas devem vir de laudo ou fonte claramente identificada.
- O teste do motor de recomendações não executa automaticamente todos os modelos ambientais.
- As recomendações retornadas são apoio à decisão e não dose de fertilizante/calcário/defensivo ou ordem de irrigação.
