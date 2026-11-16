import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import "./i18n.css";

/*
 * Idiomas do CerradoShift (PT-BR / EN).
 *
 * Como funciona: o texto em português é a própria chave. t("Texto em português")
 * devolve a tradução quando o idioma é inglês e, se não houver tradução,
 * devolve o texto original. Variáveis usam {nome}: t("Ciclo {n}", { n: 2 }).
 *
 * Para traduzir um texto novo: adicione "texto em português": "English text"
 * no objeto EN abaixo e use t("texto em português") no componente.
 */

const STORAGE_LANG = "cerradoshift_lang";

const EN = {
  // Menu e estrutura geral
  "Dashboard": "Dashboard",
  "Calculadora Agrícola": "Agricultural Calculator",
  "Mapa da Propriedade": "Farm Map",
  "Rotação de Culturas": "Crop Rotation",
  "Análises e Cenários": "Analyses & Scenarios",
  "Relatórios": "Reports",
  "Diagnóstico do Solo": "Soil Diagnostic",
  "Configurações": "Settings",
  "Página": "Page",
  "Fechar menu": "Close menu",
  "Abrir menu": "Open menu",
  "Dados da NASA": "NASA data",
  "Integração em desenvolvimento": "Integration in development",
  "Fazenda demonstrativa": "Demo farm",
  "Idioma": "Language",

  // Dashboard
  "Visão geral": "Overview",
  "Monitore sua propriedade e planeje safras mais resilientes.": "Monitor your property and plan more resilient harvests.",
  "Talhão analisado": "Selected field",
  "Consultando clima, solo e fontes ambientais da API…": "Querying climate, soil and environmental sources from the API…",
  "Não foi possível carregar os indicadores da API.": "Could not load the indicators from the API.",
  "Não foi possível atualizar os indicadores.": "Could not update the indicators.",
  "Tentar novamente": "Try again",
  "Nenhum talhão cadastrado": "No fields registered",
  "Cadastre e delimite um talhão no Mapa da Propriedade para consultar os indicadores reais.": "Register and outline a field in the Farm Map to query real indicators.",
  "Temperatura média": "Average temperature",
  "Precipitação acumulada": "Accumulated precipitation",
  "Umidade do solo": "Soil moisture",
  "Radiação solar média": "Average solar radiation",
  "MJ/m²/dia": "MJ/m²/day",
  "Sem dado disponível": "No data available",
  "A fonte não retornou este indicador para o talhão.": "The source did not return this indicator for the field.",
  "Fonte: {fonte}": "Source: {fonte}",
  "Dados retornados pela API para {nome}. Período: {inicio} a {fim}.": "Data returned by the API for {nome}. Period: {inicio} to {fim}.",
  "Estratégias de rotação": "Rotation strategies",
  "Estratégias cadastradas": "Registered strategies",
  "Consulte e gerencie as sequências na página Rotação de Culturas.": "View and manage the sequences on the Crop Rotation page.",

  // Diagnóstico do Solo (página)
  "Analise as características físicas e químicas do solo da sua propriedade.": "Analyze the physical and chemical characteristics of your property's soil.",
  "Coordenadas indisponíveis": "Coordinates unavailable",
  "Não foi possível identificar a localização geográfica deste talhão.": "Could not identify the geographic location of this field.",
  "Cadastre um talhão no Mapa da Propriedade para gerar o diagnóstico do solo.": "Register a field in the Farm Map to generate the soil diagnostic.",

  // Mapa
  "Selecione e delimite os talhões agrícolas.": "Select and outline the agricultural fields.",
  "Digite o novo nome do talhão:": "Enter the new field name:",
  "Mapa convencional": "Standard map",
  "Satélite": "Satellite",
  "Talhões cadastrados: {n}": "Registered fields: {n}",
  "hectares": "hectares",
  "Renomear": "Rename",
  "Mapa da propriedade": "Farm map",
  "{n} talhão(ões) cadastrados": "{n} field(s) registered",
  "Abrir mapa completo": "Open full map",
  "Nenhum talhão cadastrado. Acesse o mapa completo para delimitar sua propriedade.": "No fields registered. Go to the full map to outline your property.",

  // Calculadora
  "Execute os modelos científicos do CerradoShift pela API integrada.": "Run CerradoShift's scientific models through the integrated API.",
  "Parâmetros dos modelos": "Model parameters",
  "Informe os parâmetros medidos ou validados para calcular evapotranspiração pelo método dual Kc e resposta relativa da produtividade à água.": "Enter measured or validated parameters to calculate evapotranspiration using the dual Kc method and the relative yield response to water.",
  "ET₀ diária": "Daily ET₀",
  "Coeficiente basal (Kcb)": "Basal coefficient (Kcb)",
  "Fator de estresse hídrico (Ks)": "Water stress factor (Ks)",
  "Fator de redução (Kr)": "Reduction factor (Kr)",
  "Kc máximo (Kcmax)": "Maximum Kc (Kcmax)",
  "Fração de solo molhado/exposto (few)": "Fraction of wetted/exposed soil (few)",
  "ET real da cultura": "Actual crop ET",
  "ET máxima sem estresse": "Maximum ET without stress",
  "Fator de resposta do rendimento (Ky)": "Yield response factor (Ky)",
  "mm/dia": "mm/day",
  "adimensional": "dimensionless",
  "0 a 1": "0 to 1",
  "0,95": "0.95",
  "1,2": "1.2",
  "0,3": "0.3",
  "Calculando…": "Calculating…",
  "Calcular com o motor científico": "Calculate with the scientific engine",
  "Evapotranspiração dual Kc": "Dual Kc evapotranspiration",
  "ETc calculada:": "Calculated ETc:",
  "Resposta da cultura à água": "Crop response to water",
  "Redução relativa estimada:": "Estimated relative reduction:",
  "Os resultados dependem da qualidade dos parâmetros de entrada e não substituem calibração local nem avaliação de profissional agrônomo.": "Results depend on the quality of the input parameters and do not replace local calibration or assessment by an agronomist.",

  // Rotação de culturas
  "Planejamento de Rotação de Culturas": "Crop Rotation Planning",
  "Organize e compare sequências de cultivo para os talhões da propriedade.": "Organize and compare cropping sequences for the property's fields.",
  "Nova estratégia": "New strategy",
  "Nome do talhão": "Field name",
  "Selecione um talhão": "Select a field",
  "Ciclo {n}": "Cycle {n}",
  "Sequência planejada": "Planned sequence",
  "Salvar estratégia": "Save strategy",
  "Nenhuma estratégia cadastrada ainda.": "No strategies registered yet.",
  "Excluir": "Delete",
  "Informe o nome do talhão.": "Enter the field name.",

  // Culturas
  "Soja": "Soybean",
  "Milho": "Maize",
  "Feijão": "Beans",
  "Braquiária": "Brachiaria",
  "Milheto": "Pearl millet",
  "Sorgo": "Sorghum",
  "Trigo": "Wheat",
  "Algodão": "Cotton",

  // Análises e Cenários
  "Compare sequências cadastradas e avalie as relações hospedeiro–praga com o motor científico.": "Compare registered sequences and assess host–pest relationships with the scientific engine.",
  "Selecionar estratégias": "Select strategies",
  "Cadastre pelo menos duas estratégias na página Rotação de Culturas.": "Register at least two strategies on the Crop Rotation page.",
  "Estratégia A": "Strategy A",
  "Estratégia B": "Strategy B",
  "Selecione": "Select",
  "Avaliando…": "Assessing…",
  "Avaliar as duas estratégias": "Assess both strategies",
  "Talhão:": "Field:",
  "Sem identificação": "Unidentified",
  "Avaliação da sequência concluída": "Sequence assessment completed",
  "Base de dados:": "Data basis:",
  "Relações identificadas": "Identified relationships",
  "Os resultados abaixo descrevem relações presentes no catálogo de referência. Não são previsão de infestação nem garantia de controle.": "The results below describe relationships present in the reference catalog. They are not an infestation forecast or a guarantee of control.",
  "O talhão associado à estratégia {id} não foi encontrado.": "The field linked to strategy {id} was not found.",

  // Relatórios
  "Gere um documento técnico com indicadores reais, proveniência e limitações dos dados.": "Generate a technical document with real indicators, data provenance and data limitations.",
  "Consultando fontes...": "Querying sources...",
  "Gerar relatório": "Generate report",
  "Imprimir / salvar PDF": "Print / save PDF",
  "Nenhum talhão cadastrado. Cadastre um no Mapa da Propriedade.": "No fields registered. Register one in the Farm Map.",
  "Relatório técnico do talhão": "Field technical report",
  "CERRADOSHIFT · RELATÓRIO TÉCNICO": "CERRADOSHIFT · TECHNICAL REPORT",
  "Diagnóstico ambiental e agrícola": "Environmental and agricultural diagnostic",
  "Talhão selecionado": "Selected field",
  "Análise preliminar": "Preliminary analysis",
  "Emitido em:": "Issued on:",
  "Período climático:": "Climate period:",
  "{inicio} a {fim}": "{inicio} to {fim}",
  "Local:": "Location:",
  "Localização não identificada": "Location not identified",
  "Área:": "Area:",
  "ID da consulta:": "Query ID:",
  "1. Indicadores climáticos": "1. Climate indicators",
  "Precipitação": "Precipitation",
  "ET de referência (ET₀)": "Reference ET (ET₀)",
  "Maior período seco": "Longest dry spell",
  "dias": "days",
  "ET₀ e evapotranspiração real não são equivalentes. Cada indicador depende da disponibilidade da sua fonte.": "ET₀ and actual evapotranspiration are not equivalent. Each indicator depends on the availability of its source.",
  "2. Condição hídrica e riscos": "2. Water condition and risks",
  "Risco de seca (triagem):": "Drought risk (screening):",
  "Não calculado": "Not calculated",
  "alto": "high",
  "moderado": "moderate",
  "baixo": "low",
  "Déficit climático estimado:": "Estimated climate deficit:",
  "3. Diagnóstico do solo": "3. Soil diagnostic",
  "Consultando solo...": "Querying soil...",
  "Incluir diagnóstico automático de solo": "Include automatic soil diagnostic",
  "Quando a fonte não responder, o relatório indicará dados ausentes.": "When the source does not respond, the report will indicate missing data.",
  "Textura": "Texture",
  "Argila": "Clay",
  "pH em água": "pH in water",
  "Água disponível no perfil": "Available water in profile",
  "Não disponível": "Not available",
  "Origem:": "Source:",
  "Sem estimativa automática": "No automatic estimate",
  "Estado: {estado}. Lacunas: {lacunas}.": "Status: {estado}. Gaps: {lacunas}.",
  "não informado": "not reported",
  "Diagnóstico específico não consultado; exibidos apenas atributos do contexto ambiental.": "Specific diagnostic not queried; showing only attributes from the environmental context.",
  "4. Alertas ambientais": "4. Environmental alerts",
  "Nenhum alerta gerado com os dados disponíveis. Isso não comprova ausência de risco.": "No alerts generated from the available data. This does not prove the absence of risk.",
  "5. Fontes e integridade": "5. Sources and integrity",
  "Fonte": "Source",
  "Estado": "Status",
  "Cache": "Cache",
  "Sim": "Yes",
  "Não": "No",
  "Nenhuma fonte documentada na resposta.": "No source documented in the response.",
  "6. Ressalvas dos dados": "6. Data caveats",
  "CerradoShift — Documento automatizado para apoio à análise. Não substitui laudo laboratorial, validação de campo ou recomendação de engenheiro agrônomo. Simulações de rotação não estão incluídas sem resultados vinculados ao talhão.": "CerradoShift — Automated document to support analysis. It does not replace a laboratory report, field validation or an agronomist's recommendation. Rotation simulations are not included without results linked to the field.",
  "Não foi possível consultar o contexto ambiental.": "Could not query the environmental context.",
  "Não foi possível identificar as coordenadas do talhão.": "Could not identify the field's coordinates.",
  "Consulta de solo excedeu o tempo limite.": "Soil query timed out.",

  // Diagnóstico do Solo (componente)
  "Argila (%)": "Clay (%)",
  "Areia (%)": "Sand (%)",
  "Silte (%)": "Silt (%)",
  "Matéria orgânica (%)": "Organic matter (%)",
  "Capacidade de campo (m³/m³)": "Field capacity (m³/m³)",
  "Ponto de murcha (m³/m³)": "Wilting point (m³/m³)",
  "Fósforo (mg/dm³)": "Phosphorus (mg/dm³)",
  "Potássio (mg/dm³)": "Potassium (mg/dm³)",
  "Indisponível": "Unavailable",
  "Selecione um talhão com coordenadas válidas antes de consultar o solo.": "Select a field with valid coordinates before querying the soil.",
  "A profundidade deve estar entre 10 e 300 cm.": "Depth must be between 10 and 300 cm.",
  "Valor inválido: {campo}": "Invalid value: {campo}",
  "A consulta excedeu o limite de tempo.": "The query exceeded the time limit.",
  "Localização:": "Location:",
  "Nenhum talhão selecionado": "No field selected",
  "Origem dos dados": "Data source",
  "Consulta automática": "Automatic query",
  "Análise de laboratório": "Laboratory analysis",
  "Profundidade analisada (cm)": "Analyzed depth (cm)",
  "Analisando solo...": "Analyzing soil...",
  "Gerar diagnóstico": "Generate diagnostic",
  "Resultados": "Results",
  "Fonte:": "Source:",
  "Nenhuma fonte forneceu atributos quantitativos válidos": "No source provided valid quantitative attributes",
  "Confiança:": "Confidence:",
  "não informada": "not reported",
  "Modo de aquisição:": "Acquisition mode:",
  "Os provedores brasileiros foram consultados, mas ainda não forneceram atributos quantitativos válidos para o talhão.": "Brazilian providers were queried but have not yet provided valid quantitative attributes for the field.",
  "Estado dos provedores": "Provider status",
  "Estado das fontes de solo": "Soil source status",
  "sem estado": "no status",
  "Matéria orgânica": "Organic matter",
  "Água disponível": "Available water",
  "Interpretação científica": "Scientific interpretation",
  "Próxima ação:": "Next action:",
  "Avisos sobre os dados": "Data notices",
  "Resposta técnica da API": "API technical response",


  // Configurações do produtor
  'Configurações do produtor': 'Producer settings',
  'Informe as condições da propriedade e suas prioridades para personalizar as análises e recomendações do CerradoShift.': "Enter your property's conditions and priorities to customize CerradoShift analyses and recommendations.",
  'perfil preenchido': 'profile completed',
  'Preencha apenas o que você sabe.': 'Fill in only what you know.',
  'Campos desconhecidos podem ficar em branco. O CerradoShift não deve inventar valores de solo, pragas ou manejo.': 'Unknown fields can be left blank. CerradoShift must not invent soil, pest, or management values.',
  'Configuração padrão (sem talhão selecionado)': 'Default settings (no field selected)',
  'Nenhum talhão selecionado. Você pode salvar preferências gerais agora e associar os dados de manejo depois.': 'No field selected. You can save general preferences now and associate management data later.',
  'Não informado': 'Not provided',
  'Ainda não definida': 'Not yet defined',
  'Emergência': 'Emergence',
  'Vegetativo': 'Vegetative',
  'Florescimento': 'Flowering',
  'Formação / enchimento de grãos': 'Grain formation / filling',
  'Maturação': 'Maturation',
  'Próximo da colheita': 'Near harvest',
  'Desconhecida / não analisada': 'Unknown / not analyzed',
  'Presente / confirmado': 'Present / confirmed',
  'Não detectado na análise': 'Not detected in the analysis',
  'A janela em dias é apenas uma informação inicial. A viabilidade de cada cobertura também depende da época, chuva remanescente, cultivar, semeadora e manejo.': 'The window in days is only preliminary information. The feasibility of each cover crop also depends on timing, remaining rainfall, cultivar, seeder, and management.',
  'Histórico das últimas 2–3 safras': 'History of the last 2–3 growing seasons',
  'Cadastre da safra mais antiga para a mais recente. Essas informações ajudam a avaliar a sequência de hospedeiros.': 'Enter seasons from oldest to newest. This information helps assess the host sequence.',
  '+ Adicionar safra': '+ Add season',
  'Selecione': 'Select',
  'Remover': 'Remove',
  'Nenhuma safra anterior cadastrada. Adicione até três safras concluídas, se souber as informações.': 'No previous season registered. Add up to three completed seasons if you know the information.',
  'Não sei / não informado': 'Unknown / not provided',
  'Sequeiro (sem irrigação)': 'Rainfed (no irrigation)',
  'Pivô central': 'Center pivot',
  'Aspersão': 'Sprinkler',
  'Gotejamento': 'Drip irrigation',
  'Sulcos': 'Furrow irrigation',
  'Outro sistema': 'Other system',
  'Limitado': 'Limited',
  'Moderado': 'Moderate',
  'Flexível': 'Flexible',
  'Tenho limitação de disponibilidade de água': 'I have limited water availability',
  'Ex.: restrição de captação, baixa vazão, reservatório limitado ou períodos de escassez.': 'E.g., water abstraction restrictions, low flow, limited reservoir, or periods of scarcity.',
  'Maquinário disponível': 'Available machinery',
  'Água': 'Water',
  'CaCl₂': 'CaCl₂',
  'Outro / consultar laudo': 'Other / consult report',
  'Não informada': 'Not provided',
  'Arenoso': 'Sandy',
  'Franco-arenoso': 'Sandy loam',
  'Argilo-arenoso': 'Sandy clay',
  'Franco': 'Loam',
  'Argiloso': 'Clayey',
  'Muito argiloso': 'Very clayey',
  'Outra / consultar laudo': 'Other / consult report',
  'Não avaliada': 'Not assessed',
  'Suspeita': 'Suspected',
  'Confirmada por avaliação': 'Confirmed by assessment',
  'Não detectada': 'Not detected',
  'Interpretação dos nutrientes pelo laboratório': 'Laboratory interpretation of nutrients',
  'Dados físicos e valores numéricos adicionais (opcional)': 'Additional physical data and numerical values (optional)',
  'Use somente os valores que aparecem no laudo ou em medição técnica. Esses campos podem alimentar a consulta ambiental do talhão.': "Use only values shown in the report or in technical measurements. These fields may be used in the field's environmental query.",
  'A': 'A',
  'B': 'B',
  'C': 'C',
  'D': 'D',
  'Outras observações': 'Other notes',
  'Desconhecida': 'Unknown',
  'Baixa': 'Low',
  'Baixa — abordagem mais cautelosa': 'Low — more cautious approach',
  'Média': 'Medium',
  'Alta': 'High',
  'Moderada': 'Moderate',
  '+ Adicionar observação fitossanitária': '+ Add crop health observation',
  'Equilíbrio entre benefícios': 'Balance between benefits',
  'Priorizar cobertura do solo': 'Prioritize soil cover',
  'Priorizar ciclagem de nitrogênio': 'Prioritize nitrogen cycling',
  'Priorizar manejo de nematoides': 'Prioritize nematode management',
  'Alta — aceita avaliar mais alternativas': 'High — willing to consider more alternatives',
  'O que é mais importante para você?': 'What matters most to you?',
  'Culturas de transição que prefere não receber como sugestão': 'Transition crops you prefer not to receive as suggestions',
  'Salvar configurações': 'Save settings',
  'Restaurar este talhão': 'Restore this field',
  'Exportar JSON': 'Export JSON',
  'Importar JSON': 'Import JSON',
  'Os dados ficam neste navegador, no dispositivo em que foram salvos. Para compartilhar com a equipe ou mover para outro computador, use Exportar JSON. Ainda não existe login ou banco de dados multiusuário para sincronização automática.': 'Data stays in this browser, on the device where it was saved. To share with your team or move to another computer, use Export JSON. Automatic synchronization through login or a multi-user database is not yet available.',
  'Conexão com o backend': 'Backend connection',
  'Verifique se a API está disponível antes de enviar as configurações.': 'Check whether the API is available before submitting settings.',
  'Verificando conexão…': 'Checking connection…',
  'Enviando…': 'Submitting…',
  'Testar configuração na API': 'Test settings with the API',
  'O teste envia preferências, solo, manejo e rotação ao endpoint de recomendações. Nesta tela, os resultados dos modelos ambientais ainda não são calculados automaticamente; a API vai apontar os dados que faltam.': 'The test sends preferences, soil, management, and rotation data to the recommendations endpoint. Environmental model results are not calculated automatically on this screen; the API will identify missing data.',
  'Configuração recebida pela API': 'Settings received by the API',
  'Motivo:': 'Reason:',
  'Dados faltantes:': 'Missing data:',
  'Cuidados:': 'Cautions:',
  'Informações que ainda faltam': 'Information still missing',

  // Additional settings labels
  "Soja": "Soybean",
  "Milho": "Maize",
  "Algodão": "Cotton",
  "Milheto": "Pearl millet",
  "Economizar água": "Save water",
  "Eficiência hídrica e redução de perdas.": "Water-use efficiency and loss reduction.",
  "Cobrir e proteger o solo": "Cover and protect the soil",
  "Palhada, biomassa e cobertura entre safras.": "Residue, biomass, and cover between growing seasons.",
  "Ciclagem de nutrientes": "Nutrient cycling",
  "Aproveitamento e retorno de nutrientes.": "Nutrient use and return.",
  "Quebra de ciclos de pragas": "Break pest cycles",
  "Evitar continuidade de culturas hospedeiras.": "Avoid continuity of host crops.",
  "Rentabilidade": "Profitability",
  "Comparar custos, preços e receitas quando disponíveis.": "Compare costs, prices, and revenues when available.",
  "Recuperação do solo": "Soil recovery",
  "Matéria orgânica, erosão e estrutura do solo.": "Organic matter, erosion, and soil structure.",
  "Semeadora/plantadeira": "Seeder/planter",
  "Semeadora de cobertura": "Cover crop seeder",
  "Distribuidor de fertilizantes": "Fertilizer spreader",
  "Pulverizador": "Sprayer",
  "Roçadeira": "Brush cutter",
  "Rolo-faca": "Roller-crimper",
  "Triturador de palhada": "Residue shredder",
  "Subsolador": "Subsoiler",
  "Confirmado em análise/diagnóstico": "Confirmed by analysis/diagnostic",
  "Suspeito, ainda sem confirmação": "Suspected, not yet confirmed",
  "Não sei / não avaliado": "Unknown / not assessed",
  "Baixo": "Low",
  "Adequado": "Adequate",
  "Alto": "High",
  "Integrada no backend": "Integrated in backend",
  "Integração pendente — acesso aberto": "Integration pending — open access",
  "Estado não informado": "Status not provided",

  // More producer settings labels
  "Anos desde o último plantio de algodão na mesma gleba": "Years since cotton was last planted in the same field",
  "Análise de solo e fertilidade": "Soil and fertility analysis",
  "Cadastre ou desenhe um talhão na página Mapa da Propriedade.": "Register or draw a field on the Farm Map page.",
  "Classe de drenagem": "Drainage class",
  "Classe de textura do solo": "Soil texture class",
  "Compactação do solo": "Soil compaction",
  "Cultivo e planejamento de rotação": "Cropping and rotation planning",
  "Cultura comercial atual": "Current commercial crop",
  "Cultura da safra": "Season crop",
  "Data da análise": "Analysis date",
  "Data da observação": "Observation date",
  "Data de colheita": "Harvest date",
  "Data de plantio": "Planting date",
  "Declividade média (%)": "Average slope (%)",
  "Descreva outras necessidades da propriedade...": "Describe other farm needs...",
  "Dias disponíveis entre as culturas": "Days available between crops",
  "Eficiência estimada ou medida (%)": "Estimated or measured efficiency (%)",
  "Este campo também aparece na seção de rotação; os dois ficam sincronizados.": "This field also appears in the rotation section; both stay synchronized.",
  "Estágio atual da cultura": "Current crop stage",
  "Ex.: 3": "E.g., 3",
  "Ex.: 4,5": "E.g., 4.5",
  "Ex.: 5,6": "E.g., 5.6",
  "Ex.: 70": "E.g., 70",
  "Ex.: 80": "E.g., 80",
  "Ex.: Fazenda Boa Vista": "E.g., Boa Vista Farm",
  "Ex.: Safra 2024/25": "E.g., 2024/25 season",
  "Ex.: bem drenado": "E.g., well drained",
  "Ex.: evitar operações que exijam máquina não disponível; priorizar cobertura de baixo custo.": "E.g., avoid operations requiring unavailable machinery; prioritize low-cost cover crops.",
  "Ex.: ferrugem-asiática": "E.g., Asian soybean rust",
  "Grupo hidrológico": "Hydrologic group",
  "Identificação da safra": "Season identification",
  "Informe a fase observada; não precisa saber o código fenológico.": "Enter the observed stage; you do not need to know the phenological code.",
  "Informe somente se tiver medição ou dado técnico confiável.": "Enter only if you have a measurement or reliable technical data.",
  "Interpretação do pH pelo laboratório": "Laboratory pH interpretation",
  "Laboratório (opcional)": "Laboratory (optional)",
  "Laudo, local da ocorrência, sintomas observados...": "Report, location of occurrence, observed symptoms...",
  "Matéria orgânica — interpretação": "Organic matter — interpretation",
  "Método de determinação do pH": "pH determination method",
  "Necessário quando informar cultura atual e próxima cultura.": "Required when entering the current and next crops.",
  "Nome científico ou identificação": "Scientific name or identification",
  "Nome da propriedade (opcional)": "Farm name (optional)",
  "Nome do laboratório": "Laboratory name",
  "Objetivo principal para as culturas de transição": "Main goal for transition crops",
  "Observações": "Notes",
  "Observações e preferências adicionais": "Additional notes and preferences",
  "Orçamento disponível para mudanças": "Budget available for changes",
  "Pragas e problemas fitossanitários": "Pests and crop health issues",
  "Preferências e objetivos do produtor": "Producer preferences and goals",
  "Propriedade e talhão": "Farm and field",
  "Próxima cultura comercial que deseja avaliar": "Next commercial crop to assess",
  "Se não souber, deixe em branco; o relevo pode ser obtido por modelo de elevação quando integrado.": "If unknown, leave blank; terrain can be obtained from an elevation model when integrated.",
  "Severidade": "Severity",
  "Sistema de irrigação": "Irrigation system",
  "Situação": "Status",
  "Situação de Pratylenchus brachyurus": "Pratylenchus brachyurus status",
  "Talhão que deseja configurar": "Field to configure",
  "Tolerância a riscos": "Risk tolerance",
  "Use o resultado de análise nematológica, quando disponível.": "Use nematode analysis results when available.",
  "Use quando a próxima cultura for algodão.": "Use when the next crop is cotton.",
  "pH informado no laudo": "pH reported in the lab report",
  "Água e estrutura da propriedade": "Water and farm infrastructure",
  "Área do talhão (hectares)": "Field area (hectares)",

  // Settings section descriptions
  "As configurações abaixo ficam associadas ao talhão selecionado.": "The settings below are associated with the selected field.",
  "Essas escolhas ajudam a ordenar as alternativas. Não substituem viabilidade técnica ou econômica.": "These choices help rank alternatives. They do not replace technical or economic feasibility.",
  "Essas informações ajudam a interpretar o balanço hídrico e avaliar alternativas de manejo.": "This information helps interpret the water balance and assess management alternatives.",
  "O CerradoShift começa com soja, milho e algodão, além de quatro culturas de transição.": "CerradoShift starts with soybean, maize, and cotton, as well as four transition crops.",
  "Registre a interpretação do laboratório. Não estime o pH nem a necessidade de adubo pela cultura escolhida.": "Record the laboratory's interpretation. Do not estimate pH or fertilizer needs based on the selected crop.",
  "Registre apenas organismos identificados ou suspeitos. A ausência de registro não significa ausência da praga.": "Record only identified or suspected organisms. The absence of a record does not mean the pest is absent.",

  // Settings feedback messages
  "Informe de 0 a 365 dias entre as culturas para avaliar a rotação.": "Enter 0 to 365 days between crops to assess the rotation.",
  "A eficiência de irrigação deve ser maior que 0 e no máximo 100%.": "Irrigation efficiency must be greater than 0 and at most 100%.",
  "O pH deve estar entre 0 e 14, conforme o laudo.": "The pH must be between 0 and 14, as reported in the lab report.",
  "Em uma safra do histórico, a colheita está antes da data de plantio.": "In one of the historical seasons, the harvest date is before the planting date.",
  "Configurações salvas neste navegador.": "Settings saved in this browser.",
  "Dados deste talhão foram restaurados para os valores iniciais.": "This field's data has been restored to the initial values.",
  "Configuração importada e salva neste navegador.": "Settings imported and saved in this browser.",

  // Classes de textura (valores devolvidos pela API)
  "argila": "clay",
  "argila-arenosa": "sandy clay",
  "argila-siltosa": "silty clay",
  "franco": "loam",
  "franco-argilosa": "clay loam",
  "franco-argilo-arenosa": "sandy clay loam",
  "franco-argilo-siltosa": "silty clay loam",
  "franco-arenosa": "sandy loam",
  "franco-siltosa": "silt loam",
  "silte": "silt",
  "areia": "sand",
  "areia-franca": "loamy sand",
};

const FALLBACK = {
  lang: "pt",
  locale: "pt-BR",
  setLang: () => {},
  t: (text, vars) => interpolate(text, vars),
  tn: (name) => name,
};

function interpolate(text, vars) {
  if (!vars || typeof text !== "string") return text;
  return text.replace(/\{(\w+)\}/g, (match, key) =>
    vars[key] !== undefined && vars[key] !== null ? String(vars[key]) : match
  );
}

function readLang() {
  try {
    const saved = localStorage.getItem(STORAGE_LANG);
    if (saved === "en" || saved === "pt") return saved;
  } catch {
    /* sem acesso ao localStorage: usa português */
  }
  return "pt";
}

const I18nContext = createContext(FALLBACK);

export function I18nProvider({ children }) {
  const [lang, setLangState] = useState(readLang);

  useEffect(() => {
    document.documentElement.lang = lang === "en" ? "en" : "pt-BR";
  }, [lang]);

  const setLang = useCallback((next) => {
    const value = next === "en" ? "en" : "pt";
    setLangState(value);
    try {
      localStorage.setItem(STORAGE_LANG, value);
    } catch {
      /* ignora */
    }
  }, []);

  const value = useMemo(() => {
    const t = (text, vars) => {
      const base = lang === "en" ? (EN[text] ?? text) : text;
      return interpolate(base, vars);
    };
    // Nomes padrão de talhão ("Talhão 1") aparecem como "Field 1" em inglês.
    // O nome salvo no navegador não é alterado.
    const tn = (name) => {
      if (lang !== "en" || typeof name !== "string") return name;
      return name.replace(/^Talhão (\d+)$/, "Field $1");
    };
    return { lang, locale: lang === "en" ? "en-US" : "pt-BR", setLang, t, tn };
  }, [lang, setLang]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n() {
  return useContext(I18nContext);
}

export function LanguageSwitch() {
  const { lang, setLang, t } = useI18n();
  return (
    <div className="lang-switch" role="group" aria-label={t("Idioma")}>
      <button
        type="button"
        className={lang === "pt" ? "active" : ""}
        aria-pressed={lang === "pt"}
        onClick={() => setLang("pt")}
      >
        PT
      </button>
      <button
        type="button"
        className={lang === "en" ? "active" : ""}
        aria-pressed={lang === "en"}
        onClick={() => setLang("en")}
      >
        EN
      </button>
    </div>
  );
}
