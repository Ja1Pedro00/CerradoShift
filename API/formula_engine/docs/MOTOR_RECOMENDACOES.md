# Motor de recomendações — CerradoShift

## O que faz

O endpoint `POST /api/v1/assessments/recommendations` interpreta resultados já calculados (balanço hídrico, índices de vegetação, erosão e análise térmica), dados de solo, observações de pragas, rotação planejada e preferências do produtor. A resposta contém recomendações estruturadas, justificativas, prioridade, confiança, dados faltantes e salvaguardas.

Este é um **motor inicial baseado em regras transparentes**, não um sistema especialista validado em campo.

## Como executar

Na pasta `cerradoshift_api`:

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Abra `http://127.0.0.1:8000/docs`, escolha `POST /api/v1/assessments/recommendations`, clique em **Try it out**, cole o JSON de `examples/recommendations_request.json` e execute.

## Exemplo de integração

O backend deve executar os módulos na ordem necessária e repassar suas respostas dentro de `model_results`:

```python
payload = {
    "current_commercial_crop": "soybean",
    "field": {"irrigation_system": "center_pivot", "irrigation_efficiency": 0.82},
    "soil_test": None,
    "pests": [],
    "preferences": {"priorities": ["water_saving", "soil_cover"]},
    "rotation": {
        "current_crop": "soybean",
        "next_crop": "cotton",
        "days_available": 70,
        "pratylenchus_brachyurus_status": "unknown"
    },
    "model_results": {
        "water_balance": resposta_do_endpoint_field,
        "vegetation": {
            "mean_indices": resposta_dos_indices["mean_indices"],
            "z_score": resposta_da_anomalia["z_score"]
        },
        "erosion": resposta_do_endpoint_erosion,
        "phenology_thermal": resposta_do_endpoint_thermal
    }
}
```

No exemplo acima, `resposta_do_endpoint_*` representa o dicionário JSON retornado pelos endpoints correspondentes. O frontend não deve recalcular os indicadores: deve coletar as informações, chamar a API e exibir as recomendações.

## Campos de entrada

- `current_commercial_crop`: `soybean`, `maize` ou `cotton`.
- `field`: área, declividade, sistema de irrigação, eficiência informada, limitação de água, maquinário e orçamento.
- `soil_test`: interpretação do laboratório para pH, P, K, S, Ca, Mg, N e matéria orgânica.
- `pests`: IDs de organismos, estado (`confirmed`, `suspected`, `not_detected`, `unknown`) e severidade.
- `preferences.priorities`: `water_saving`, `soil_cover`, `nutrient_cycling`, `pest_break`, `profitability` e `soil_recovery`.
- `preferences.objective`: objetivo da triagem de cobertura (`balanced`, `ground_cover`, `nitrogen_cycling`, `nematode_management`).
- `rotation`: culturas atual/próxima, dias disponíveis e situação de *Pratylenchus brachyurus*.
- `crop_history`: últimas safras concluídas, em ordem cronológica, com cultura e datas opcionais; amplia a sequência usada nas regras de hospedeiros.
- `model_results`: respostas dos outros endpoints.

Os campos de solo aceitam `low`, `adequate`, `high` ou `unknown` como interpretação do laboratório. Não se deve transformar um valor bruto de pH, P ou K em uma classe usando um limite universal: método analítico, profundidade, textura, CTC, cultura e recomendações estaduais importam.

## Recomendações possíveis nesta versão

1. Água/irrigação: investigar estresse, conferir umidade na zona radicular, auditar eficiência e uniformidade, avaliar perdas e estudar viabilidade de irrigação suplementar.
2. Fertilidade: pedir análise de solo, revisar acidez, P/K/S/Ca/Mg, plano de N e nodulação da soja. O motor **não fornece dose de adubo, calcário ou gesso**.
3. Solo: avaliar aporte de palhada/cobertura e diagnosticar compactação antes de qualquer intervenção.
4. Vegetação: recomendar vistoria quando anomalia NDVI/EVI for muito negativa; não diagnostica praga ou doença por satélite.
5. Erosão: recomendar avaliação de conservação somente quando a perda RUSLE puder ser comparada com uma tolerância local informada.
6. Fitossanidade/rotação: indicar monitoramento e verificar relações conhecidas de hospedeiro; para *P. brachyurus*, priorizar avaliação de crotalárias específicas e não presumir ausência do nematoide.
7. Preferências: influenciam a ordenação qualitativa das opções e o tipo de explicação. Não criam viabilidade econômica sem custos/preços reais.

## Como interpretar a saída

Cada item de `recommendations` possui:

- `id`: identificador estável para o frontend.
- `category`: área da recomendação.
- `priority`: `high`, `medium` ou `low`.
- `title` e `recommended_action`: o que fazer/avaliar.
- `why_this_was_recommended`: variáveis/gatilhos que acionaram a regra.
- `confidence`: qualidade da base disponível, não probabilidade estatística de sucesso.
- `missing_data`: dados que melhorariam a avaliação.
- `safeguards`: limites e verificações antes de agir.
- `sources`: referências quando disponíveis.
- `is_automatic_prescription`: permanece sempre `false`.

`data_gaps` informa dados ausentes que o frontend pode transformar em tarefas para o produtor.

## Integração com frontend

- Método: `POST`
- URL local: `http://127.0.0.1:8000/api/v1/assessments/recommendations`
- Cabeçalho: `Content-Type: application/json`
- Corpo: JSON conforme `examples/recommendations_request.json`.
- Resposta: JSON com `recommendations`, `data_gaps`, `preferences_applied` e `mandatory_review`.

O frontend deve renderizar a prioridade, o título, a ação, o motivo e os avisos. Não deve esconder `safeguards` nem converter `confidence` em promessa de acerto.

## Limitações e próximas validações

- Gatilho de auditoria de irrigação abaixo de 70% é um parâmetro inicial configurável, não norma universal.
- O motor não escolhe automaticamente entre pivô, aspersão, gotejamento ou sulco. Ele indica sistemas/opções que podem ser estudados; a decisão exige projeto hidráulico, solo, topografia, cultura, energia, custos e disponibilidade de água.
- Não há prescrição de defensivos ou diagnóstico de doenças.
- O catálogo de hospedeiros é pequeno e regional; ausência de registro significa desconhecido, não não-hospedeiro.
- O score de rentabilidade não é calculado sem custos, preços e produtividade local.
- Limites de fertilidade devem vir de laudos interpretados com recomendações regionais.
- Regras e parâmetros devem ser revisados por engenheiro-agrônomo e validados em talhões reais antes de uso operacional.


## Histórico de safras no cadastro do produtor

O campo `crop_history` aceita até seis safras/culturas de transição nos identificadores `soybean`, `maize`, `cotton`, `millet`, `urochloa_ruziziensis`, `crotalaria_spectabilis` e `crotalaria_ochroleuca`. Na interface do MVP, o produtor pode cadastrar até três entradas, da mais antiga para a mais recente. Ausência de relação no catálogo continua sendo classificada como desconhecida; nunca é interpretada como não hospedeira.
