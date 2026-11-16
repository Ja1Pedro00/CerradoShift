"""Motor explicável de recomendações do CerradoShift — MVP Cerrado.

O módulo interpreta resultados de outros modelos, dados informados pelo produtor,
observações fitossanitárias e preferências. Ele gera ações de triagem, nunca uma
prescrição automática de dose de fertilizante, pesticida ou lâmina de irrigação.

Regras deliberadamente conservadoras:
- não diagnostica praga/doença por NDVI;
- não calcula dose de adubo/calcário sem calibração regional e laudo interpretado;
- não ordena troca de sistema de irrigação sem estudo hidráulico/econômico;
- não presume que praga ausente do catálogo esteja ausente no campo.
"""
from __future__ import annotations

from typing import Any

from formula_engine.core.cerrado_mvp import recommend_transition_options
from formula_engine.core.pest_rotation import assess_rotation_sequence, PEST_HOST_REFERENCES

ENGINE_VERSION = "0.1.0"

TRANSITION_LABELS = {
    "millet": "Milheto",
    "urochloa_ruziziensis": "Urochloa ruziziensis (braquiária-ruziziensis)",
    "crotalaria_spectabilis": "Crotalária-espectábilis",
    "crotalaria_ochroleuca": "Crotalária-ochroleuca",
}

KNOWN_PEST_IDS = set(PEST_HOST_REFERENCES) | {"pratylenchus_brachyurus"}


def _number(mapping: dict[str, Any], key: str) -> float | None:
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _recommendation(
    *,
    rec_id: str,
    category: str,
    priority: str,
    title: str,
    action: str,
    why: list[str],
    confidence: str = "medium",
    missing_data: list[str] | None = None,
    safeguards: list[str] | None = None,
    sources: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    return {
        "id": rec_id,
        "category": category,
        "priority": priority,
        "title": title,
        "recommended_action": action,
        "why_this_was_recommended": why,
        "confidence": confidence,
        "missing_data": missing_data or [],
        "safeguards": safeguards or [],
        "sources": sources or [],
        "is_automatic_prescription": False,
    }


def _derive_rotation_objective(preferences: dict[str, Any], nematode_status: str) -> str:
    if nematode_status == "present":
        return "nematode_management"
    explicit = preferences.get("objective", "balanced")
    if explicit != "balanced":
        return explicit
    priorities = preferences.get("priorities", [])
    if "nutrient_cycling" in priorities:
        return "nitrogen_cycling"
    if "soil_cover" in priorities or "soil_recovery" in priorities:
        return "ground_cover"
    if "pest_break" in priorities:
        return "nematode_management"
    return "balanced"


def _build_rotation_recommendation(request: dict[str, Any], recs: list[dict[str, Any]], gaps: list[str]) -> None:
    rotation = dict(request.get("rotation") or {})
    # Um diagnóstico fitossanitário confirmado informado na lista de pragas
    # também atualiza o estado do nematoide usado na triagem da rotação.
    for observation in request.get("pests", []):
        if observation.get("pest_id") == "pratylenchus_brachyurus" and observation.get("status") == "confirmed":
            rotation["pratylenchus_brachyurus_status"] = "present"
    current = rotation.get("current_crop")
    following = rotation.get("next_crop")
    if not current or not following:
        gaps.append("Informe a cultura comercial atual, a próxima cultura e os dias disponíveis para avaliar plantas de transição.")
        return

    prefs = request.get("preferences") or {}
    if not request.get("crop_history"):
        gaps.append("Histórico das últimas 2–3 safras não informado; isso limita a avaliação de continuidade de culturas hospedeiras.")
    nematode_status = rotation.get("pratylenchus_brachyurus_status", "unknown")
    objective = _derive_rotation_objective(prefs, nematode_status)
    if nematode_status == "unknown" and prefs.get("risk_tolerance") == "low":
        # Preferir uma triagem mais cautelosa; não significa que o nematoide esteja presente.
        objective = "nematode_management"
    options = recommend_transition_options(
        current_crop=current,
        next_crop=following,
        days_available=int(rotation.get("days_available", 0)),
        pratylenchus_brachyurus_status=nematode_status,
        objective=objective,
        cotton_years_since_last=(request.get("field") or {}).get("cotton_years_since_last"),
    )
    excluded = set(prefs.get("avoided_transition_crops", []))
    candidates = []
    for candidate in options["candidates"]:
        if candidate["crop_id"] in excluded:
            continue
        if candidate["suitability"] == "not_applicable_no_sowing_window":
            continue
        candidates.append(candidate)

    if options.get("cotton_return_warning"):
        recs.append(_recommendation(
            rec_id="cotton_return_interval",
            category="rotation_and_phytosanitary",
            priority="high",
            title="Verificar intervalo de retorno do algodão",
            action="Antes de planejar o algodão, confirme o intervalo exigido para a gleba, o vazio sanitário e as regras fitossanitárias vigentes para o município/estado.",
            why=[options["cotton_return_warning"]],
            confidence="medium",
            safeguards=["Não tratar o intervalo de dois anos como regra legal universal; verificar norma vigente e orientação técnica local."],
        ))

    if not candidates:
        recs.append(_recommendation(
            rec_id="no_transition_candidate",
            category="rotation",
            priority="medium",
            title="Não foi possível recomendar uma planta de transição",
            action="Reavaliar a janela de semeadura, as espécies evitadas e o diagnóstico fitossanitário. Manter e manejar a palhada existente pode ser uma alternativa a avaliar.",
            why=options["warnings"],
            confidence="low",
            missing_data=["Janela local de semeadura", "Cultivar e manejo pretendido", "Diagnóstico nematológico quando houver suspeita"],
        ))
        return

    # Ranking é somente correspondência com a preferência declarada; não é
    # produtividade prevista nem uma pontuação agronômica validada.
    recs.append(_recommendation(
        rec_id="transition_crop_options",
        category="rotation",
        priority="high" if nematode_status == "present" else "medium",
        title="Avaliar culturas de transição entre as culturas comerciais",
        action="Compare as opções abaixo com o calendário local, a disponibilidade de água, a cultivar, o custo da semente e a operação de semeadura/manejo.",
        why=[f"Objetivo usado para ordenar as opções: {objective}.", "A ordem considera as funções agronômicas cadastradas e as regras fitossanitárias iniciais; não é previsão de produtividade."],
        confidence="medium" if nematode_status != "unknown" else "low",
        missing_data=["Data prevista de semeadura e chuva remanescente", "Cultivar da planta de cobertura", "Análise nematológica se o histórico ou sintomas justificarem"],
        safeguards=["Ausência de diagnóstico não significa ausência de nematoides.", "Milheto e Urochloa podem multiplicar Pratylenchus brachyurus; não os considerar seguros quando o status for desconhecido.", "Não converter automaticamente esta lista em recomendação de plantio."],
        sources=[
            {"name": "Embrapa — plantas de cobertura e manejo no Cerrado", "url": "https://www.infoteca.cnptia.embrapa.br/infoteca/bitstream/doc/943518/1/COT371.pdf"},
            {"name": "Embrapa — plantas de cobertura em sucessão ao algodão", "url": "https://www.embrapa.br/en/busca-de-publicacoes/-/publicacao/1157023/cover-plants-in-second-crop-nutrients-in-straw-and-cotton-yield-in-succession"},
        ],
    ))
    recs[-1]["candidate_options"] = candidates
    recs[-1]["rotation_warnings"] = options["warnings"]
    recs[-1]["ranking_basis"] = "ordem qualitativa orientada às preferências; não representa score de produtividade ou lucro"
    if not (request.get("field") or {}).get("available_machinery"):
        gaps.append("Maquinário disponível para semeadura, manejo e dessecação das plantas de transição não informado.")

    # Avaliação fitossanitária de organismos já cobertos pela pequena base.
    detected = [p["pest_id"] for p in request.get("pests", []) if p.get("status") in {"confirmed", "suspected"}]
    if detected:
        mapped = [p for p in detected if p in PEST_HOST_REFERENCES]
        history_sequence = [
            item.get("crop_id")
            for item in (request.get("crop_history") or [])
            if item.get("crop_id")
        ]
        sequence = history_sequence + [current, following]
        if mapped:
            assessment = assess_rotation_sequence(sequence, mapped)
            host_messages = [item for t in assessment["transitions"] for item in t["pests"]]
            if host_messages:
                recs.append(_recommendation(
                    rec_id="pest_host_rotation_check",
                    category="pest_management",
                    priority="high" if any(p.get("status") == "confirmed" for p in request.get("pests", [])) else "medium",
                    title="Verificar continuidade de hospedeiros na rotação",
                    action="Use a relação hospedeiro–cultura como triagem e confirme espécie, cultivar, plantas daninhas hospedeiras e diagnóstico com assistência técnica.",
                    why=[item["interpretation"] for item in host_messages],
                    confidence="medium",
                    safeguards=[assessment["overall_note"]],
                ))
        unknown_detected = [p for p in detected if p not in KNOWN_PEST_IDS]
        if unknown_detected:
            recs.append(_recommendation(
                rec_id="unmapped_pest_observation",
                category="pest_management",
                priority="high" if any(p.get("status") == "confirmed" for p in request.get("pests", [])) else "medium",
                title="Organismo observado ainda não possui regra no catálogo",
                action="Registrar identificação laboratorial ou validação de um engenheiro-agrônomo e acrescentar a relação hospedeiro–cultura ao catálogo regional.",
                why=[f"IDs sem regra validada: {', '.join(unknown_detected)}."],
                confidence="low",
                missing_data=["Identificação taxonômica", "Localidade e data da ocorrência", "Cultura/cultivar e severidade"],
            ))


def generate_recommendations(payload: dict[str, Any]) -> dict[str, Any]:
    """Interpreta dados do talhão e devolve recomendações explicáveis.

    Espera dicionário compatível com RecommendationRequest.model_dump().
    Os subdicionários model_results devem conter respostas dos endpoints já
    executados (water_balance, vegetation, erosion, phenology_thermal etc.).
    """
    request = payload
    field = request.get("field") or {}
    soil = request.get("soil_test")
    pests = request.get("pests") or []
    preferences = request.get("preferences") or {}
    model_results = request.get("model_results") or {}
    recs: list[dict[str, Any]] = []
    gaps: list[str] = []
    warnings: list[str] = [
        "As recomendações são apoio à decisão e não substituem responsável técnico, análise laboratorial, diagnóstico fitossanitário ou normas locais.",
        "Não são calculadas doses de fertilizantes, calcário, defensivos nem lâminas finais de irrigação neste motor.",
    ]

    # 1) Água e irrigação: usa os campos gerados pelo endpoint /assessments/field.
    water = model_results.get("water_balance") or {}
    ks = _number(water, "latest_ks")
    depletion = _number(water, "latest_depletion_mm")
    raw = _number(water, "latest_raw_mm")
    stress_days = _number(water, "water_stress_days")
    runoff = _number(water, "cumulative_runoff_mm")
    deep_drainage = _number(water, "cumulative_deep_percolation_mm")
    irrigation_rec = water.get("irrigation_recommendation") or {}

    if ks is not None:
        if ks < 0.90 or (depletion is not None and raw is not None and depletion >= raw):
            recs.append(_recommendation(
                rec_id="water_stress_action",
                category="irrigation_and_water",
                priority="high" if ks < 0.70 else "medium",
                title="Investigar possível estresse hídrico",
                action="Conferir a umidade do solo em mais de uma profundidade da zona radicular, verificar previsão de chuva e avaliar a programação de irrigação antes de aplicar água.",
                why=[f"O balanço hídrico retornou Ks={ks:.2f}."] + ([f"A depleção estimada ({depletion:.1f} mm) alcançou/superou RAW ({raw:.1f} mm)."] if depletion is not None and raw is not None else []),
                confidence="medium",
                missing_data=["Leitura recente de umidade na zona radicular", "Previsão de chuva de curto prazo", "Verificação da uniformidade do sistema"],
                safeguards=[f"Lâmina líquida indicativa do modelo: {irrigation_rec.get('suggested_net_depth_mm')} mm, se fornecida. Não aplicar sem conferir umidade, infiltração e capacidade do sistema."],
            ))
        elif ks >= 0.90:
            recs.append(_recommendation(
                rec_id="water_status_monitor",
                category="irrigation_and_water",
                priority="low",
                title="Manter monitoramento hídrico",
                action="Continuar acompanhando umidade na zona radicular e chuva; evitar irrigação baseada somente no calendário.",
                why=[f"O último Ks calculado foi {ks:.2f}; o balanço não indicou redução relevante de ET pelo limiar de triagem usado."],
                confidence="medium",
            ))
    else:
        gaps.append("Resultado do balanço hídrico não informado: sem Ks, depleção e RAW não é possível avaliar o estresse de água.")

    if field.get("irrigation_system") == "rainfed" and ks is not None and ks < 0.90:
        recs.append(_recommendation(
            rec_id="supplemental_irrigation_feasibility",
            category="irrigation_system",
            priority="medium",
            title="Avaliar viabilidade de irrigação suplementar",
            action="Estudar disponibilidade legal de água, vazão, energia, infraestrutura, custo e retorno antes de considerar irrigação suplementar.",
            why=["O sistema informado é de sequeiro e o balanço indicou possível estresse hídrico."],
            confidence="low",
            missing_data=["Disponibilidade e outorga de água", "Vazão e pressão disponíveis", "Custo de energia e investimento", "Levantamento topográfico/hidráulico"],
            safeguards=["O resultado não significa que a irrigação seja econômica, legal ou tecnicamente viável."],
        ))

    efficiency = field.get("irrigation_efficiency")
    system = field.get("irrigation_system", "unknown")
    if system not in {"rainfed", "unknown"} and efficiency is not None and efficiency < 0.70:
        recs.append(_recommendation(
            rec_id="irrigation_efficiency_audit",
            category="irrigation_system",
            priority="high",
            title="Fazer auditoria de eficiência e uniformidade da irrigação",
            action="Medir vazão, pressão, uniformidade de distribuição, vazamentos e lâmina aplicada. Comparar a manutenção do sistema atual com alternativas somente após estudo técnico e econômico.",
            why=[f"A eficiência informada ({efficiency:.0%}) está abaixo do limiar de triagem de 70% configurado para gerar investigação."],
            confidence="medium",
            missing_data=["Teste de uniformidade de distribuição", "Vazão/pressão por setor", "Tipo de solo e taxa de infiltração", "Custo de energia e investimento"],
            safeguards=["O limiar de 70% é um gatilho operacional configurável, não uma norma universal nem prova de defeito.", "Não recomendar troca automática para gotejamento, pivô ou aspersão sem projeto hidráulico."],
        ))
        system_options = {
            "center_pivot": ["auditar bocais, reguladores de pressão e uniformidade", "avaliar baixa pressão e automação/setorização", "comparar com irrigação localizada somente se cultura, solo, topografia e custos justificarem"],
            "sprinkler": ["auditar pressão, bocais, vento e uniformidade", "avaliar setorização e programação noturna quando operacionalmente adequada", "comparar com pivô ou irrigação localizada após estudo técnico-econômico"],
            "drip": ["verificar filtragem, pressão, entupimento e uniformidade dos emissores", "avaliar setorização, manejo da fertirrigação e manutenção", "não alterar o sistema sem verificar qualidade da água e compatibilidade do solo/cultura"],
            "furrow": ["avaliar nivelamento, comprimento dos sulcos, vazão de entrada e tempo de oportunidade", "comparar aspersão/pivô ou gotejamento considerando relevo, infiltração, energia e investimento"],
            "other": ["realizar diagnóstico hidráulico do sistema e comparar alternativas compatíveis com a propriedade"],
        }.get(system, ["identificar o sistema instalado e realizar diagnóstico hidráulico antes de comparar alternativas"])
        recs[-1]["system_options_to_evaluate"] = system_options
    elif system == "unknown":
        gaps.append("Tipo de irrigação não informado; necessário para avaliar eficiência e possíveis mudanças no sistema.")

    if "water_saving" in preferences.get("priorities", []) and system not in {"rainfed", "unknown"} and efficiency is None:
        recs.append(_recommendation(
            rec_id="measure_irrigation_efficiency",
            category="irrigation_system",
            priority="medium",
            title="Medir eficiência e uniformidade do sistema de irrigação",
            action="Registrar lâminas aplicadas e fazer teste de uniformidade por setor; medir umidade do solo antes/depois da irrigação para ajustar turno e duração.",
            why=["Economia de água foi selecionada como prioridade, mas a eficiência do sistema não foi informada."],
            confidence="medium",
            missing_data=["Eficiência medida", "Vazão e pressão", "Lâmina aplicada por evento", "Umidade do solo antes/depois"],
        ))

    if field.get("water_limited"):
        recs.append(_recommendation(
            rec_id="water_availability_plan",
            category="irrigation_system",
            priority="medium",
            title="Planejar o uso da água disponível",
            action="Mapear a disponibilidade legal e sazonal de água, medir vazão e demanda por setor, revisar horários e turnos de irrigação e avaliar alternativas de maior controle somente com projeto técnico e econômico.",
            why=["O produtor informou limitação de disponibilidade de água."],
            confidence="low",
            missing_data=["Vazão disponível por período", "Outorga/licença e restrições de captação", "Demanda das culturas por fase", "Custo de energia e operação"],
            safeguards=["A escolha entre pivô, aspersão, gotejamento ou outro sistema depende de solo, topografia, cultura, vento, energia, investimento e manutenção; não há um sistema universalmente melhor."],
        ))

    if (runoff is not None and runoff > 0) or (deep_drainage is not None and deep_drainage > 0):
        reasons = []
        if runoff is not None and runoff > 0:
            reasons.append(f"O balanço estimou {runoff:.1f} mm de escoamento acumulado.")
        if deep_drainage is not None and deep_drainage > 0:
            reasons.append(f"O balanço estimou {deep_drainage:.1f} mm de drenagem profunda acumulada.")
        recs.append(_recommendation(
            rec_id="water_loss_investigation",
            category="irrigation_and_water",
            priority="medium",
            title="Investigar perdas por escoamento ou drenagem",
            action="Conferir se a intensidade de chuva/irrigação supera a infiltração, observar enxurradas e verificar a lâmina aplicada por setor. Considerar parcelamento da aplicação quando tecnicamente adequado.",
            why=reasons,
            confidence="low",
            missing_data=["Dados de chuva por evento", "Taxa de infiltração", "Cobertura e declividade do talhão"],
            safeguards=["Os valores podem refletir a simplificação do modelo diário e precisam de confirmação em campo."],
        ))

    # 2) Solo e fertilidade: somente interpreta classes fornecidas pelo laboratório.
    if soil is None:
        gaps.append("Análise de solo não fornecida; não é seguro sugerir correção ou dose de fertilizante.")
        recs.append(_recommendation(
            rec_id="soil_sampling",
            category="fertility",
            priority="high",
            title="Realizar análise de solo antes de definir adubação",
            action="Coletar amostras representativas por talhão e profundidade, enviar a laboratório e registrar a interpretação regional de pH, P, K, matéria orgânica e demais parâmetros relevantes.",
            why=["Sem análise de solo e calibração regional, o sistema não consegue distinguir deficiência, suficiência ou excesso de nutrientes."],
            confidence="high",
            missing_data=["pH e método de análise", "P e K com método laboratorial", "Matéria orgânica/carbono", "CTC, saturação por bases e textura", "Profundidade e identificação do talhão"],
        ))
    else:
        if soil.get("sample_date"):
            # Data antiga é apenas sinal para pedir revisão; a validade depende do sistema e manejo.
            gaps.append("Verifique se a análise de solo ainda representa o talhão e o manejo atuais.")
        ph_status = soil.get("ph_status", "unknown")
        if ph_status == "low":
            recs.append(_recommendation(
                rec_id="soil_acidity_review",
                category="fertility",
                priority="high",
                title="Avaliar correção da acidez do solo",
                action="Solicitar interpretação do laudo por profissional habilitado para avaliar necessidade e dose de calcário, considerando método de pH, CTC, saturação por bases, textura, profundidade e cultura.",
                why=["O laudo foi informado como indicativo de pH baixo."],
                confidence="medium",
                missing_data=["Método de pH", "CTC e saturação por bases", "Alumínio e cálcio/magnésio", "Profundidade de incorporação"],
                safeguards=["Não calcular dose de calcário apenas pelo valor de pH; a recomendação depende do método regional."],
            ))
        elif ph_status == "high":
            recs.append(_recommendation(
                rec_id="soil_high_ph_review",
                category="fertility",
                priority="medium",
                title="Investigar pH elevado e disponibilidade de micronutrientes",
                action="Conferir laudo completo, histórico de calagem e análise foliar; pedir avaliação local antes de qualquer tentativa de acidificação.",
                why=["O laboratório classificou o pH como elevado."],
                confidence="medium",
                safeguards=["Não aplicar acidificantes ou micronutrientes sem diagnóstico específico."],
            ))

        nutrient_status = soil.get("nutrient_status") or {}
        for nutrient in ("P", "K", "S", "Ca", "Mg"):
            status = nutrient_status.get(nutrient, "unknown")
            if status == "low":
                recs.append(_recommendation(
                    rec_id=f"nutrient_{nutrient.lower()}_review",
                    category="fertility",
                    priority="high",
                    title=f"Avaliar manejo de {nutrient} indicado como baixo no laudo",
                    action=f"Solicitar recomendação de correção/manutenção de {nutrient} baseada no método do laboratório, textura, CTC, expectativa de rendimento, cultura e recomendações oficiais para a região.",
                    why=[f"A interpretação laboratorial fornecida classificou {nutrient} como baixo."],
                    confidence="medium",
                    missing_data=["Método analítico e unidade", "CTC/textura", "Meta de produtividade", "Histórico de adubação e exportação"],
                    safeguards=["Este motor não fornece dose em kg/ha; não usar concentração isolada como dose de fertilizante."],
                ))
            elif status == "high":
                recs.append(_recommendation(
                    rec_id=f"nutrient_{nutrient.lower()}_avoid_excess",
                    category="fertility",
                    priority="medium",
                    title=f"Evitar aplicação adicional de {nutrient} sem justificativa",
                    action="Conferir recomendação regional, balanço de exportação e análise foliar antes de acrescentar esse nutriente ao plano de adubação.",
                    why=[f"O laudo fornecido classificou {nutrient} como alto."],
                    confidence="medium",
                    safeguards=["Não significa suspensão automática: considerar cultura, expectativa de rendimento, método e histórico."],
                ))

        n_status = nutrient_status.get("N", "unknown")
        if n_status == "unknown":
            gaps.append("Interpretação de nitrogênio (N) ausente ou desconhecida; considerar histórico da cultura, matéria orgânica, fixação biológica e recomendação regional.")
        crop = request.get("current_commercial_crop") or (request.get("rotation") or {}).get("current_crop")
        if n_status == "low" and crop in {"maize", "cotton"}:
            recs.append(_recommendation(
                rec_id="nitrogen_plan_review",
                category="fertility",
                priority="high",
                title="Revisar o plano de nitrogênio da cultura",
                action="Conferir análise, cultura anterior, matéria orgânica, meta de rendimento e estádio para definir parcelamento e fonte com assistência agronômica local.",
                why=[f"O status de N foi informado como baixo para a cultura {crop}."],
                confidence="medium",
                safeguards=["O motor não calcula dose de N nem substitui recomendação regional."],
            ))
        elif crop == "soybean":
            recs.append(_recommendation(
                rec_id="soybean_biological_n_fixation_check",
                category="fertility",
                priority="low",
                title="Verificar nodulação e inoculação da soja",
                action="Registrar histórico de inoculação, condições de armazenamento/aplicação do inoculante e observar nodulação em plantas representativas com assistência técnica.",
                why=["A soja depende da fixação biológica de nitrogênio quando adequadamente estabelecida; a avaliação de nodulação é mais informativa que presumir necessidade de adubação nitrogenada."],
                confidence="medium",
                safeguards=["Não aplicar nitrogênio como correção automática com base apenas em um status genérico."],
            ))

        if soil.get("organic_matter_status") == "low":
            recs.append(_recommendation(
                rec_id="organic_matter_cover",
                category="soil_conservation",
                priority="medium",
                title="Aumentar aporte de resíduos e cobertura do solo",
                action="Avaliar plantas de cobertura e manutenção de palhada compatíveis com a janela de semeadura e o diagnóstico de nematoides; monitorar matéria orgânica ao longo de vários ciclos.",
                why=["A interpretação laboratorial indicou matéria orgânica baixa."],
                confidence="medium",
                safeguards=["Aumento de matéria orgânica é gradual e depende de biomassa, decomposição, clima e manejo; não é efeito imediato de uma única safra."],
            ))

        if soil.get("compaction_status") in {"suspected", "confirmed"}:
            recs.append(_recommendation(
                rec_id="soil_compaction_diagnosis",
                category="soil_conservation",
                priority="high" if soil.get("compaction_status") == "confirmed" else "medium",
                title="Diagnosticar compactação antes de decidir intervenção",
                action="Mapear resistência à penetração em diferentes umidades, densidade do solo, infiltração e distribuição das raízes; delimitar as zonas afetadas antes de avaliar qualquer operação mecânica.",
                why=[f"O estado de compactação foi informado como {soil.get('compaction_status')} ."],
                confidence="medium" if soil.get("compaction_status") == "confirmed" else "low",
                safeguards=["Não recomendar escarificação/subsolagem automaticamente: intervenção sem diagnóstico pode elevar custo e não resolver a causa."],
            ))

        # Explicita campos laboratoriais que não receberam interpretação local.
        if ph_status == "unknown":
            gaps.append("O laudo não trouxe classificação local de pH (baixo/adequado/alto); não interpretar pH bruto com faixa universal.")
        for nutrient in ("P", "K", "S", "Ca", "Mg"):
            if nutrient not in nutrient_status or nutrient_status.get(nutrient) == "unknown":
                gaps.append(f"Interpretação laboratorial de {nutrient} ausente ou desconhecida.")

    # 3) Pragas: não converter observação espectral em diagnóstico.
    for pest in pests:
        pest_id = pest.get("pest_id", "unknown")
        status = pest.get("status", "unknown")
        if status in {"confirmed", "suspected"}:
            recs.append(_recommendation(
                rec_id=f"pest_scout_{pest_id}",
                category="pest_management",
                priority="high" if status == "confirmed" else "medium",
                title="Confirmar e monitorar a ocorrência fitossanitária",
                action="Registrar pontos de ocorrência, estágio da cultura, intensidade, data e método de identificação; confirmar organismo e população com profissional/laboratório antes de selecionar controle.",
                why=[f"O produtor informou ocorrência {status} de {pest_id}."],
                confidence="medium" if status == "confirmed" else "low",
                missing_data=["Identificação/diagnóstico", "Distribuição espacial no talhão", "Severidade ou densidade populacional", "Cultivar e estádio"],
                safeguards=["Não recomendar defensivo, dose ou intervalo de aplicação sem diagnóstico, registro legal e receituário quando exigido."],
            ))
        elif status == "unknown":
            gaps.append(f"Status fitossanitário desconhecido para {pest_id}; ausência de registro não significa ausência do organismo.")

    # 4) Anomalia de vegetação e calor: gatilhos de vistoria, não diagnóstico.
    vegetation = model_results.get("vegetation") or {}
    anomaly_z = _number(vegetation, "anomaly_z")
    if anomaly_z is None:
        anomaly_z = _number(vegetation, "z_score")
    ndvi = _number(vegetation, "ndvi_mean")
    if ndvi is None:
        mean_indices = vegetation.get("mean_indices") or {}
        ndvi = _number(mean_indices, "ndvi")
    if anomaly_z is not None and anomaly_z <= -2:
        recs.append(_recommendation(
            rec_id="vegetation_anomaly_scout",
            category="field_scouting",
            priority="high",
            title="Inspecionar áreas com anomalia negativa de vegetação",
            action="Fazer vistoria georreferenciada e cruzar o mapa com umidade do solo, estágio, falhas de plantio, nutrição, pragas e doenças.",
            why=[f"A anomalia padronizada informada foi Z={anomaly_z:.2f}, abaixo de -2."],
            confidence="medium",
            safeguards=["NDVI/EVI baixo não identifica sozinho seca, deficiência nutricional, praga ou doença."],
        ))
    elif ndvi is None and anomaly_z is None:
        gaps.append("Índices de vegetação/anomalia não informados; não é possível usar sensoriamento remoto na interpretação.")

    thermal = model_results.get("phenology_thermal") or {}
    heat_days = _number(thermal, "high_temperature_days")
    if heat_days is None:
        heat_days = _number(thermal, "heat_days_above_configured_threshold")
    if heat_days is not None and heat_days > 0:
        recs.append(_recommendation(
            rec_id="heat_stress_scout",
            category="climate_risk",
            priority="medium",
            title="Vistoriar possíveis efeitos de calor na fase atual",
            action="Conferir fase fenológica e sintomas, acompanhar umidade do solo e consultar limites térmicos validados para cultivar e fase antes de alterar o manejo.",
            why=[f"O modelo registrou {int(heat_days)} dia(s) acima do limite térmico informado."],
            confidence="low",
            missing_data=["Limite validado para cultivar/fase", "Duração horária do calor", "Observação de campo"],
        ))

    # 5) Erosão: só comparar com tolerância local explicitamente fornecida.
    erosion = model_results.get("erosion") or {}
    soil_loss = _number(erosion, "soil_loss_t_ha_year")
    if soil_loss is None:
        soil_loss = _number(erosion, "estimated_sheet_rill_soil_loss_t_ha_year")
    tolerance = _number(erosion, "tolerable_soil_loss_t_ha_year")
    if soil_loss is not None and tolerance is not None and soil_loss > tolerance:
        recs.append(_recommendation(
            rec_id="erosion_control",
            category="soil_conservation",
            priority="high",
            title="Priorizar medidas de conservação do solo",
            action="Avaliar cobertura permanente, manutenção de palhada, plantio em nível, faixas vegetadas e práticas mecânicas dimensionadas por técnico conforme relevo e legislação local.",
            why=[f"A perda estimada ({soil_loss:.2f} t/ha/ano) supera a tolerância local informada ({tolerance:.2f} t/ha/ano)."],
            confidence="medium",
            safeguards=["RUSLE é uma estimativa de erosão laminar e em sulcos; confirme fatores, unidade, escala e tolerância local."],
        ))
    elif soil_loss is not None and tolerance is None:
        gaps.append("Há estimativa RUSLE, mas falta o limite de perda tolerável de solo definido para o solo/localidade.")
    elif soil_loss is None and "soil_recovery" in preferences.get("priorities", []):
        gaps.append("A recuperação do solo foi selecionada como prioridade, mas ainda faltam estimativa de erosão e dados de cobertura/relevo para avaliá-la.")

    # 6) Rotação e transição: usa o catálogo regional atual e preferências.
    _build_rotation_recommendation(request, recs, gaps)

    # Preferências e viabilidade econômica.
    if "profitability" in preferences.get("priorities", []):
        economics = model_results.get("economics") or {}
        if not economics.get("crop_costs") or not economics.get("expected_prices"):
            gaps.append("Preferência por rentabilidade registrada, mas faltam custos locais, preços, produtividade de referência e operação das culturas para comparar margens.")

    if field.get("budget_level") == "low":
        warnings.append("Orçamento limitado informado: comparar custo de semente, implantação, dessecação/manejo, maquinário e oportunidade de plantio antes de selecionar cobertura ou trocar irrigação.")

    # Ordenação transparente por prioridade, sem escore oculto.
    priority_order = {"high": 0, "medium": 1, "low": 2}
    recs.sort(key=lambda item: (priority_order[item["priority"]], item["category"], item["id"]))

    if not recs:
        recs.append(_recommendation(
            rec_id="insufficient_indicators",
            category="data_quality",
            priority="medium",
            title="Dados insuficientes para recomendações específicas",
            action="Comece enviando o resultado do balanço hídrico, cultura atual, tipo de irrigação, análise de solo e histórico fitossanitário.",
            why=["Nenhum gatilho de recomendação pôde ser avaliado com os dados recebidos."],
            confidence="low",
            missing_data=gaps,
        ))

    return {
        "engine_version": ENGINE_VERSION,
        "scope": "Cerrado brasileiro — MVP soja, milho, algodão e culturas de transição",
        "status": "recommendations_generated" if recs else "insufficient_data",
        "recommendations": recs,
        "data_gaps": sorted(set(gaps)),
        "preferences_applied": preferences,
        "interpretation": "Motor baseado em regras explícitas e resultados fornecidos; não é sistema especialista validado em campo e não emite prescrição de dose ou aplicação.",
        "mandatory_review": "Validar as ações com engenheiro-agrônomo e dados locais antes de executar operações de irrigação, calagem, adubação, controle fitossanitário ou mudança de rotação.",
    }
