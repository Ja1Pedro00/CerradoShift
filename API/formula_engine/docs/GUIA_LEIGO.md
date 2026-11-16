# CerradoShift — guia do MVP Cerrado para entender o projeto sem conhecimento de APIs

Este texto explica o primeiro MVP do CerradoShift. Para começar de forma simples, o escopo foi limitado ao Cerrado brasileiro, com soja, milho e algodão como culturas comerciais e milheto, Urochloa ruziziensis, Crotalaria spectabilis e Crotalaria ochroleuca como culturas de transição.


## 0. O que a primeira versão vai avaliar

Pense em três culturas que geram receita e em plantas que podem ser cultivadas entre elas ou em consórcio para deixar o solo mais protegido.

**Culturas comerciais:** soja, milho e algodão.

**Culturas de transição:**
- Milheto: ajuda a produzir palhada e cobrir o solo.
- Urochloa ruziziensis (braquiária-ruziziensis): pode produzir cobertura e ser consorciada com milho.
- Crotalaria spectabilis e Crotalaria ochroleuca: leguminosas usadas em cobertura/adubação verde e que podem ser opções em áreas com certos nematoides.

Uma planta de transição não é automaticamente boa para toda área. No Cerrado, a Embrapa alerta que milheto e braquiárias podem multiplicar o nematoide-das-lesões (*Pratylenchus brachyurus*) em certas condições. As crotalárias spectabilis e ochroleuca aparecem como opções mais apropriadas para esse problema nas referências consultadas. Por isso, o sistema pergunta se esse nematoide já foi identificado. Se o produtor não souber, a aplicação registra a informação como desconhecida, não como ausência.

A aplicação também deve perguntar quantos dias há entre a colheita e o plantio seguinte. No Cerrado, a chuva restante da estação condiciona o estabelecimento da cobertura; sem água ou janela suficiente, pode ser melhor manter a palhada já existente do que sugerir uma nova semeadura.

## 1. O que é uma API? Pense em um restaurante

Imagine o CerradoShift como um restaurante:

- **Você (produtor)** faz um pedido na tela: informa onde fica o talhão, qual cultura planta, como é o solo e o que deseja comparar.
- **A interface (frontend)** é o cardápio e o garçom. Ela mostra campos, mapas, gráficos e recebe os dados.
- **A API** é o balcão que recebe o pedido, confere se as informações estão completas e encaminha cada parte para o setor correto.
- **Os módulos matemáticos** são a cozinha: calculam água, vegetação, erosão, temperatura e relações entre culturas e pragas.
- **As fontes externas** são os fornecedores: NASA, mapas de solo, bancos fitossanitários, estações e laboratórios.
- **A resposta da API** é o prato que volta para a tela: números, gráficos, alertas e explicações.

A API não é o site e não é um satélite. É a parte do sistema que organiza pedidos e devolve resultados calculados.

## 2. O que acontece desde que o produtor abre o aplicativo

### Passo 1 — Delimitar o terreno

O produtor procura a propriedade no mapa e desenha o contorno do talhão (ou importa um arquivo de limites). O sistema precisa guardar latitude/longitude e a forma exata da área.

Por que isso importa? Porque o satélite não deve analisar um ponto aleatório perto da fazenda: precisa separar os pixels que estão dentro do talhão. O backend atual recebe latitude e longitude para o clima, mas ainda não faz a extração espacial completa a partir de um polígono.

### Passo 2 — Buscar o contexto ambiental

A aplicação consulta serviços diferentes:

- **NASA POWER:** fornece histórico meteorológico e radiação para a coordenada. Esta conexão já está feita para dados diários.
- **GPM IMERG:** pode fornecer chuva estimada por satélite, inclusive em intervalos subdiários. A conexão ainda precisa ser construída.
- **HLS (Landsat + Sentinel-2):** fornece reflectância da superfície que permite observar a vegetação em escala de dezenas de metros. A conexão de download/recorte e qualidade ainda falta.
- **SMAP:** ajuda a acompanhar a umidade da camada superficial do solo. O produto não mede toda a água disponível para raízes.
- **SoilGrids:** fornece estimativas globais de algumas propriedades do solo, como textura, pH e carbono orgânico. São mapas de previsão, não laudos de laboratório.
- **Modelo de elevação:** ajuda a saber se o talhão é plano ou inclinado, necessário para estudar erosão.

É como montar um quebra-cabeça: cada fornecedor traz uma peça diferente, numa escala diferente. O aplicativo não deve fingir que todas as peças têm a mesma precisão.

### Passo 3 — Entender o vigor da vegetação com NDVI e outros índices

O satélite registra a luz que a superfície reflete em diferentes faixas. A vegetação costuma refletir bastante no infravermelho próximo (NIR) e absorver parte da luz vermelha.

O NDVI compara essas duas faixas:

\[
NDVI=\frac{NIR-Red}{NIR+Red}
\]

- Valores mais altos normalmente indicam maior presença/cobertura de vegetação verde.
- Valores mais baixos podem indicar pouca vegetação, solo exposto, senescência ou estresse.
- Um valor baixo não diz, sozinho, se a causa é falta de água, praga, doença, deficiência nutricional ou apenas o estágio normal da cultura.

O CerradoShift também calcula, quando as bandas necessárias estão presentes:

| Índice | Em termos simples | Para que ajuda |
|---|---|---|
| NDVI | Verde e densidade de vegetação | Acompanhar o desenvolvimento ao longo do tempo. |
| EVI | Parecido com NDVI, mas corrige melhor alguns efeitos atmosféricos e do fundo da copa | Melhor discriminação em vegetação densa. |
| SAVI e MSAVI2 | Índices que reduzem a influência do solo visível | Áreas com plantas pequenas ou solo exposto. |
| NDMI | Usa infravermelho e onda curta | Mudanças relacionadas à água no dossel. |
| NDWI verde-NIR | Compara verde e infravermelho | Identificação de água superficial; não confundir com NDMI. |
| NBR e NBR2 | Comparam bandas de infravermelho | Mudanças de vegetação e impactos de fogo. |

**O que já está implementado:** as fórmulas, validações das bandas e médias dos pixels enviados. Também há um endpoint de anomalia padronizada (z-score): ele compara o índice atual com uma média e um desvio-padrão históricos que precisam ser informados.  
**O que falta:** buscar imagens HLS, aplicar escala correta, remover nuvens/sombras/neve com a máscara de qualidade, recortar a imagem pelo polígono do talhão, construir a série histórica por época fenológica e gerar automaticamente suas médias/desvios. Sem isso, o endpoint calcula índices para os valores recebidos, mas não busca automaticamente imagens do satélite.

### Passo 4 — Calcular a demanda de água

Primeiro calculamos ET₀, que é a evapotranspiração de referência. Pense nela como a demanda de água de uma vegetação padrão imaginária.

A FAO-56 Penman–Monteith usa temperatura, umidade do ar, vento, radiação e altitude. Depois, a cultura corrige essa demanda com Kc:

\[
ET_c=K_c\times ET_0
\]

Exemplo simples: se ET₀ do dia for 5 mm e Kc for 1,2, a demanda potencial da cultura será 6 mm naquele dia.

O sistema atual já calcula ET₀ e ETc por uma curva de quatro fases. Os valores de Kc e a duração das fases precisam vir de uma fonte adequada à espécie, cultivar e sistema de produção. Não existe um Kc único para todo milho, soja ou trigo do mundo.

### Passo 5 — Saber se o solo tem água suficiente

O sistema usa três conceitos:

- **TAW:** quanto de água o perfil de solo pode disponibilizar entre capacidade de campo e ponto de murcha.
- **RAW:** quanto dessa reserva pode ser usado antes de começar o estresse, segundo a cultura.
- **Ks:** fator que reduz a evapotranspiração quando a água disponível se torna insuficiente.

Para calcular isso com confiança, precisamos de capacidade de campo, ponto de murcha, profundidade de raízes e umidade inicial. Mapas globais podem dar uma aproximação, mas sensor e análise de solo melhoram bastante a avaliação.

O modelo atual acompanha diariamente a água que entra como chuva e irrigação, desconta evapotranspiração e estima drenagem/escoamento. É um modelo de uma reserva radicular simplificada. Ainda faltam camadas mais detalhadas de solo, infiltração calibrada, ascensão capilar e integração total do método dual Kc.

### Passo 6 — Observar crescimento e calor

O GDD (graus-dia de crescimento) é uma maneira de somar o calor útil acumulado pela cultura acima de uma temperatura-base.

Por exemplo: se uma cultura tiver temperatura-base de 10 °C e a média diária for 20 °C, o dia soma aproximadamente 10 graus-dia.

O backend já calcula GDD por dia e acumulado, além de contar dias acima do limite térmico informado. Falta cadastrar limiares específicos de desenvolvimento e calor para cada cultivar e usar esses limiares para controlar automaticamente a troca de fases no balanço.

### Passo 7 — Avaliar risco de erosão

A RUSLE estima perda média de solo por erosão laminar e em pequenos sulcos. Ela combina:

- R: força erosiva da chuva;
- K: facilidade de o solo ser erodido;
- LS: comprimento e inclinação da rampa;
- C: cobertura e manejo;
- P: práticas de conservação.

O código implementa a multiplicação dos fatores. Porém, o usuário ou o provedor ainda precisam fornecer fatores corretos. O aplicativo não deve converter um NDVI em fator C automaticamente sem uma calibração regional.

### Passo 8 — Considerar pragas e doenças na rotação

A rotação não funciona apenas pelo nome ou família da cultura. A pergunta correta é: a praga consegue se alimentar ou se reproduzir na cultura seguinte? Há plantas daninhas hospedeiras? O organismo sobrevive no solo? A variedade tem resistência?

No primeiro MVP, o problema fitossanitário escolhido para orientar a seleção de coberturas é o nematoide-das-lesões (*Pratylenchus brachyurus*). A Embrapa alerta que o nematoide pode ocorrer em soja, milho e algodão, e que braquiárias e algumas cultivares de milheto também podem ser hospedeiras e multiplicadoras. As crotalárias *C. spectabilis* e *C. ochroleuca* aparecem como opções com baixa ou nenhuma reprodução desse nematoide nas referências consultadas. Isso não significa que sejam solução universal: é necessário confirmar a espécie de nematoide e consultar a recomendação regional.

A API não diagnostica o nematoide. Ela pergunta se o produtor já tem análise confirmando presença, ausência detectada ou se a situação é desconhecida. Se for desconhecida, a aplicação mantém a incerteza e não afirma que qualquer cobertura é segura. Os antigos catálogos amplos do protótipo não fazem parte do fluxo ativo deste MVP.

### Passo 9 — Comparar cenários de rotação

Nesta primeira versão, a aplicação compara uma cultura comercial atual com a próxima e mostra coberturas de transição candidatas. Depois, o motor deverá comparar sequências mais longas. Exemplos:

- manter o sistema atual;
- substituir uma cultura por uma espécie de cobertura;
- testar uma leguminosa ou uma cultura comercial alternativa;
- planejar uma sequência de três a cinco anos.

Cada cenário deve mostrar benefícios e custos: consumo de água, cobertura, erosão, fertilidade, riscos de pragas, calendário, custo operacional e possibilidade de venda.

**Esta etapa ainda não está completa no código.** Temos catálogo, uma primeira verificação de hospedeiros e modelos ambientais separados, mas ainda não há um otimizador de rotação ou uma pontuação global validada. Pesos precisam ser definidos com o produtor e podem variar conforme seus objetivos.

## 3. O que é cada rota/endereço da API

Pense num endereço de serviço como uma opção específica do balcão.

| Endereço | Significado | O que enviar/receber |
|---|---|---|
| `GET /api/v1/health` | “Está funcionando?” | Não exige dados. Retorna estado do servidor. |
| `GET /api/v1/data-sources` | “Quais fornecedores estão ligados?” | Retorna fontes e estado de integração. |
| `GET /api/v1/cerrado-mvp/catalog` | “Quais culturas estão disponíveis nesta primeira versão?” | Retorna soja, milho, algodão e as quatro opções de transição. |
| `POST /api/v1/assessments/cerrado-transition-options` | “Quais coberturas posso avaliar entre duas culturas comerciais?” | Recebe cultura atual, próxima cultura, dias disponíveis, objetivo e situação de *P. brachyurus*. |
| `GET /api/v1/crop-catalog` | “Quais perfis hídricos de referência existem?” | Retorna os poucos parâmetros de referência já cadastrados. |
| `POST /api/v1/assessments/field` | “Avalie a água deste talhão.” | Recebe local, cultura, clima, solo e irrigação. |
| `POST /api/v1/assessments/vegetation-indices` | “Calcule os índices desses pixels.” | Recebe reflectâncias de superfície. |
| `POST /api/v1/assessments/vegetation-anomaly` | “Este NDVI está diferente do normal para a área?” | Compara um índice atual com média e desvio-padrão de referência. |
| `POST /api/v1/assessments/erosion` | “Calcule a estimativa RUSLE.” | Recebe os fatores R, K, LS, C e P. |
| `POST /api/v1/assessments/phenology-thermal` | “Some o calor acumulado e conte exposição térmica.” | Recebe Tmax/Tmin, temperatura-base e limite. |
| `POST /api/v1/assessments/rotation` | “Veja como a sucessão se relaciona com pragas conhecidas.” | Recebe sequência de culturas e IDs de pragas. |
| `POST /api/v1/assessments/dual-kc` | “Calcule evaporação do solo e transpiração separadamente.” | Recebe Kcb, Ks, Kr, Ke/limites e ET₀. |
| `POST /api/v1/assessments/yield-water-response` | “Qual a resposta relativa à falta de água?” | Recebe ET real, ET máxima e Ky calibrado. |

- `GET` significa consultar algo.
- `POST` significa enviar informações para o sistema processar.
- O texto e os números enviados geralmente são colocados em um pacote chamado **JSON**. Pense nele como um formulário organizado que os computadores conseguem ler.

## 4. Como iniciar o sistema no computador

1. Instale Python 3.11 ou superior.
2. Abra o terminal na pasta `cerradoshift_api`.
3. Crie um ambiente virtual e instale os pacotes:

```bash
python -m venv .venv
source .venv/bin/activate       # macOS/Linux
# .venv\\Scripts\\activate    # Windows
pip install -r requirements.txt
```

4. Inicie a API:

```bash
uvicorn app.main:app --reload
```

5. Abra no navegador `http://127.0.0.1:8000/docs`.

Essa página é um painel automático para testar cada endereço sem escrever um aplicativo de tela. Você pode abrir uma operação, preencher os campos e clicar em “Execute”.

Para testar se tudo está correto:

```bash
pytest -q
```

## 5. O que o pacote contém e o que ainda não contém

| Já existe | Ainda falta construir |
|---|---|
| Backend Python com FastAPI. | Aplicativo visual React, mapas interativos e painel do produtor. |
| Integração diária NASA POWER. | Conectar GPM, SMAP, SoilGrids e aquisição HLS. |
| ET₀, ETc simples e balanço hídrico diário. | Modelo hídrico multicamada e Kcb+Ke integrado. |
| Cálculo de índices de vegetação e anomalia padronizada a partir de reflectância/estatística informada. | Pipeline automático de imagens, polígonos, máscara QA e geração da série temporal. |
| GDD, risco térmico de triagem, RUSLE com fatores fornecidos. | Calibrar variáveis globais e obter R/K/C/P de fontes consistentes. |
| Catálogo do MVP com soja, milho, algodão e quatro coberturas candidatas; triagem inicial de *P. brachyurus*. | Catálogo de parâmetros agronômicos por cultivar/região e base fitossanitária abrangente. |
| Testes automatizados. | Banco de dados, cadastro de propriedades, autenticação, histórico e implantação em nuvem. |

## 6. Está matematicamente completo?

Não. O núcleo matemático necessário para uma primeira demonstração está parcialmente implementado, mas ainda faltam componentes para uma avaliação agrícola confiável para o Cerrado.

**Já há fórmulas codificadas:** ET₀ FAO-56, ETc por Kc simples, TAW/RAW/Ks, balanço diário simplificado, NDVI/EVI e outros índices, GDD, triagem de calor, RUSLE com fatores informados, Kc dual isolado e resposta de rendimento à água isolada.

**Falta integrar ou calibrar:** aquisição e processamento real das imagens, mapas e sensores; geração automática da série histórica e comparação sazonal; parâmetros por espécie/cultivar/local; balanço de água de várias camadas; fenologia por GDD; estimativa de fatores RUSLE; nutrição e salinidade; previsão e diagnóstico fitossanitário regional; produtividade absoluta com modelo de biomassa e índice de colheita; economia; otimização de rotação; propagação de incerteza e validação por dados de campo.

A aplicação só deve mostrar uma recomendação forte quando a origem dos dados, a validade geográfica, a incerteza e as condições locais estiverem claras. O resultado correto pode ser “dados insuficientes para recomendar”, em vez de inventar uma resposta.

**Atenção a uma integração planejada:** o serviço REST do SoilGrids está temporariamente pausado pelo ISRIC. Para construir essa integração, é melhor avaliar WCS, WebDAV ou dados SoilGrids já disponibilizados no Google Earth Engine, sem depender de uma API REST instável.
