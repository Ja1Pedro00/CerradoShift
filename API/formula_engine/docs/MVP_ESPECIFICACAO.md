# CerradoShift — especificação do primeiro MVP

## Objetivo

Construir uma versão pequena e explicável para apoiar a comparação de rotações no Cerrado brasileiro. O escopo inicial tem três culturas comerciais e quatro espécies de transição/cobertura. A plataforma não fará prescrição agronômica automática: apresentará opções, razões, alertas e lacunas de informação.

## 1. Culturas do primeiro MVP

### Comerciais

| ID interno | Cultura | Nome científico | Família | Observações para o sistema |
|---|---|---|---|---|
| `soybean` | Soja | *Glycine max* | Fabaceae | Exigir cultivar e data de semeadura para parametrizar fenologia e água. |
| `maize` | Milho | *Zea mays* | Poaceae | Distinguir primeira safra e safrinha; permitir consórcio com Urochloa. |
| `cotton` | Algodão | *Gossypium hirsutum* | Malvaceae | Considerar histórico de talhão, restos culturais e intervalo de retorno. |

### Transição / cobertura / adubação verde

| ID interno | Espécie | Funções principais | Cuidado importante |
|---|---|---|---|
| `millet` | Milheto (*Cenchrus americanus*, sin. *Pennisetum glaucum*) | Biomassa, palhada, cobertura e ciclagem de nutrientes. | Algumas cultivares podem hospedar e multiplicar *Pratylenchus brachyurus*. |
| `urochloa_ruziziensis` | *Urochloa ruziziensis* | Palhada persistente, cobertura, raízes e consórcio com milho. | Braquiárias podem hospedar e multiplicar *P. brachyurus*. |
| `crotalaria_spectabilis` | *Crotalaria spectabilis* | Adubação verde, fixação biológica de N e manejo específico de nematoides. | Referências consultadas indicam não hospedeira ou reprodução mínima de *P. brachyurus*. Não generalizar para outras crotalárias. |
| `crotalaria_ochroleuca` | *Crotalaria ochroleuca* | Adubação verde, fixação biológica de N e manejo específico de nematoides. | Referências consultadas indicam não hospedeira ou reprodução mínima de *P. brachyurus*. Confirmar localmente. |

**Não incluir nesta primeira versão:** sorgo, girassol, arroz, guandu ou outras culturas comerciais. Para a fase 2, os candidatos comerciais iniciais são sorgo e girassol; como futuras transições, podem ser avaliados guandu e estilosantes. Eles só entram depois de parametrização e revisão fitossanitária específicas.

## 2. Por que essas plantas de transição?

A Embrapa descreve milheto, espécies de *Urochloa*, crotalárias e guandu como opções usadas na entressafra do Cerrado. A semeadura indicada no material consultado ocorre entre o fim de janeiro e o início de março; quanto mais tarde a implantação, menor tende a ser a água disponível e o desenvolvimento da cobertura. A janela não deve ser codificada como data fixa: deve ser confrontada com chuva, localidade, solo e operação da propriedade.

Em estudo da Embrapa Algodão sobre coberturas na segunda safra após soja e seus efeitos no algodão em sucessão, foram avaliadas *Urochloa ruziziensis*, milheto, *C. spectabilis*, *C. ochroleuca*, guandu e consórcios. O estudo reforça que as espécies não cumprem a mesma função e que a escolha deve refletir o objetivo do produtor.

## 3. Regra fitossanitária inicial

A primeira regra específica será a situação de *Pratylenchus brachyurus* (nematoide-das-lesões), porque afeta soja, milho e algodão e pode alterar radicalmente a escolha das coberturas.

- Se o nematoide estiver confirmado, o MVP não deve priorizar milheto ou Urochloa como opção padrão.
- *C. spectabilis* e *C. ochroleuca* podem aparecer como candidatas para validação técnica, conforme a espécie de nematoide e o diagnóstico laboratorial.
- O sistema deve deixar explícito que a rotação não elimina o nematoide e que plantas daninhas e hospedeiros alternativos precisam ser controlados.
- Não agrupar todas as espécies de crotalária. *C. juncea*, por exemplo, não deve receber automaticamente a mesma classificação de *C. spectabilis* ou *C. ochroleuca*.
- Quando o produtor não souber a situação nematológica, o estado será `unknown`, nunca presumido como ausência.

Para o algodão, a aplicação também emitirá alerta quando o retorno à mesma gleba ocorrer em menos de dois anos. Essa é uma regra de cautela baseada na referência da Embrapa consultada e deverá ser confirmada por recomendação regional, cultivar e programa fitossanitário.

## 4. Sequências que o MVP deve conseguir explorar

As sequências a seguir são hipóteses para comparação, não calendários universais:

1. **Soja → Crotalaria spectabilis/ochroleuca → algodão.** Avaliar a janela de implantação, água, espécie de nematoide e manejo da cobertura.
2. **Soja → milho safrinha consorciado com Urochloa ruziziensis.** O milho é uma cultura comercial e a Urochloa entra como cobertura; a recomendação deve ser condicionada a janela, manejo e diagnóstico de *P. brachyurus*.
3. **Milho → milheto ou crotalária → soja.** Comparar biomassa e cobertura com a função fitossanitária específica; não favorecer milheto se houver *P. brachyurus* confirmado.
4. **Algodão → cobertura adequada à janela → soja ou milho.** Avaliar palhada, nematoides, resíduos, janela de semeadura e intervalo de retorno do algodão.

A cultura de transição não precisa aparecer entre todas as duas culturas comerciais. Ela pode ser implantada na segunda safra, em entressafra ou em consórcio, conforme a janela disponível. O sistema deve reconhecer que soja seguida de milho safrinha é uma sucessão no mesmo ano agrícola; alternar apenas essas duas culturas repetidamente não garante, por si só, toda a diversificação de uma rotação.

## 5. Dados mínimos solicitados ao produtor

1. Localização do talhão (idealmente polígono; para protótipo, latitude/longitude e área).
2. Cultura atual e próxima cultura comercial desejada.
3. Histórico das culturas no talhão nas últimas 2–3 safras, incluindo datas aproximadas de plantio e colheita.
4. Número estimado de dias entre colheita e próximo plantio.
5. Situação conhecida de *P. brachyurus*: presente, não detectado em análise ou desconhecido.
6. Textura do solo e análise química, se disponíveis; o sistema mantém os campos desconhecidos sem inventar valores.
7. Sistema de irrigação e disponibilidade de água, quando houver.

## 6. O que o motor faz agora

O endpoint `/api/v1/assessments/cerrado-transition-options` devolve uma lista qualitativa de opções de cobertura. Ele:

- valida se a cultura comercial atual e a próxima são soja, milho ou algodão;
- considera dias disponíveis e objetivo (equilíbrio, cobertura, ciclagem de N ou manejo de nematoides);
- rebaixa milheto e Urochloa quando *P. brachyurus* está confirmado;
- prioriza crotalárias específicas como candidatas técnicas nessa situação;
- emite alerta para retorno do algodão em menos de dois anos;
- informa que a lista não é uma prescrição nem uma previsão de produtividade.

A ordem é baseada em regras transparentes, não em um índice numérico de eficácia. O sistema ainda não calcula biomassa esperada, produtividade, lâmina de água, economia ou redução percentual de nematoides para cada espécie.

## 7. Próximas etapas, sem ampliar o escopo de culturas ainda

1. Integrar calendário de semeadura e dados climáticos NASA POWER por talhão.
2. Conectar aquisição e recorte de imagens HLS; calcular NDVI/EVI e série temporal do talhão.
3. Criar perfis hídricos referenciados para soja, milho, algodão e as coberturas; parametrizar por cultivar, fase e manejo.
4. Integrar o balanço hídrico com o estabelecimento das coberturas e a água disponível para a cultura seguinte.
5. Adicionar análise de solo e fatores de erosão; não inferir pH ou nutrientes a partir da cultura escolhida.
6. Expandir regras fitossanitárias com fontes regionais e espécie/cultivar/hospedeiro confirmado.
7. Só então adicionar duas novas culturas comerciais e suas respectivas coberturas.

## Referências técnicas iniciais

- Embrapa. [Cultivo de plantas de cobertura para os sistemas de produção no Cerrado](https://digital.agrishow.com.br/artigos/cultivo-de-plantas-de-cobertura-para-os-sistemas-de-produo-no-cerrado-2/).
- Embrapa Algodão. [Plantas que Minimizar Problemas do Sistema de Produção do Algodoeiro no Cerrado](https://www.infoteca.cnptia.embrapa.br/infoteca/bitstream/doc/943518/1/COT371.pdf).
- Ferreira et al. Embrapa Algodão. [Cover plants in second crop: nutrients in straw and cotton yield in succession](https://www.embrapa.br/en/busca-de-publicacoes/-/publicacao/1157023/cover-plants-in-second-crop-nutrients-in-straw-and-cotton-yield-in-succession).
- Embrapa Ageitec. [Rotação de culturas](https://www.embrapa.br/web/agencia-de-informacao-tecnologica/tematicas/sistema-plantio-direto/fazendo-certo/planejando-e-executando/fase-de-implantacao/organizando-o-sistema-produtivo/rotacao-de-culturas).
