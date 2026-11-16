"""Catálogo e regras iniciais do MVP CerradoShift para o Cerrado brasileiro.

Escopo: soja, milho e algodão como culturas comerciais; milheto,
Urochloa ruziziensis e crotalárias específicas como culturas de transição.
As regras são de triagem e não substituem diagnóstico ou recomendação técnica local.
"""

COMMERCIAL_CROPS = {
    "soybean": {
        "name_pt": "Soja",
        "scientific_name": "Glycine max (L.) Merr.",
        "family": "Fabaceae",
        "role": "commercial",
        "main_notes": [
            "Cultura anual de verão de grande importância no Cerrado.",
            "O perfil hídrico e fenológico deve ser parametrizado por cultivar e data de semeadura.",
        ],
        "profile_status": "crop_identity_ready_local_parameters_required",
    },
    "maize": {
        "name_pt": "Milho",
        "scientific_name": "Zea mays L.",
        "family": "Poaceae",
        "role": "commercial",
        "main_notes": [
            "Distinguir milho de primeira safra e milho segunda safra (safrinha).",
            "Consórcio com Urochloa pode ser considerado para formar palhada, conforme janela e manejo.",
        ],
        "profile_status": "crop_identity_ready_local_parameters_required",
    },
    "cotton": {
        "name_pt": "Algodão",
        "scientific_name": "Gossypium hirsutum L.",
        "family": "Malvaceae",
        "role": "commercial",
        "main_notes": [
            "Exige atenção elevada ao histórico de nematoides e ao manejo de restos culturais.",
            "O retorno do algodão à mesma gleba deve respeitar intervalo fitossanitário regional; a referência Embrapa consultada indica no mínimo dois anos.",
        ],
        "profile_status": "crop_identity_ready_local_parameters_required",
    },
}

TRANSITION_CROPS = {
    "millet": {
        "name_pt": "Milheto",
        "scientific_name": "Cenchrus americanus (sin. Pennisetum glaucum)",
        "family": "Poaceae",
        "role": "cover_or_transition",
        "main_functions": ["biomassa e palhada", "cobertura do solo", "ciclagem de nutrientes"],
        "fitosanitary_notes": [
            "Algumas cultivares podem hospedar e multiplicar Pratylenchus brachyurus; não indicar automaticamente em áreas com esse nematoide.",
        ],
        "evidence_status": "regional_reference_cerrado",
    },
    "urochloa_ruziziensis": {
        "name_pt": "Urochloa ruziziensis (braquiária-ruziziensis)",
        "scientific_name": "Urochloa ruziziensis",
        "family": "Poaceae",
        "role": "cover_or_transition",
        "main_functions": ["biomassa e palhada persistente", "cobertura do solo", "raízes e estruturação do perfil", "consórcio com milho"],
        "fitosanitary_notes": [
            "Braquiárias podem hospedar e multiplicar Pratylenchus brachyurus; verificar diagnóstico antes de indicar.",
        ],
        "evidence_status": "regional_reference_cerrado",
    },
    "crotalaria_spectabilis": {
        "name_pt": "Crotalária-espectábilis",
        "scientific_name": "Crotalaria spectabilis Roth",
        "family": "Fabaceae",
        "role": "cover_or_transition",
        "main_functions": ["adubação verde", "fixação biológica de nitrogênio", "raiz pivotante", "manejo específico de nematoides"],
        "fitosanitary_notes": [
            "Em referências da Embrapa, é não hospedeira ou permite reprodução mínima de Pratylenchus brachyurus; confirmar espécie, população e recomendação local.",
            "Não confundir com Crotalaria juncea, que pode ser suscetível a P. brachyurus.",
        ],
        "evidence_status": "regional_reference_cerrado",
    },
    "crotalaria_ochroleuca": {
        "name_pt": "Crotalária-ochroleuca",
        "scientific_name": "Crotalaria ochroleuca G. Don",
        "family": "Fabaceae",
        "role": "cover_or_transition",
        "main_functions": ["adubação verde", "fixação biológica de nitrogênio", "manejo específico de nematoides"],
        "fitosanitary_notes": [
            "Em referências da Embrapa, é não hospedeira ou permite reprodução mínima de Pratylenchus brachyurus; confirmar espécie, população e recomendação local.",
        ],
        "evidence_status": "regional_reference_cerrado",
    },
}

SOURCES = [
    {
        "title": "Cultivo de plantas de cobertura para os sistemas de produção no Cerrado",
        "organization": "Embrapa Algodão",
        "url": "https://digital.agrishow.com.br/artigos/cultivo-de-plantas-de-cobertura-para-os-sistemas-de-produo-no-cerrado-2/",
        "supports": ["milheto", "Urochloa", "crotalárias", "guandu", "janela de semeadura e formação de palhada"],
    },
    {
        "title": "Plantas que Minimizar Problemas do Sistema de Produção do Algodoeiro no Cerrado",
        "organization": "Embrapa Algodão",
        "url": "https://www.infoteca.cnptia.embrapa.br/infoteca/bitstream/doc/943518/1/COT371.pdf",
        "supports": ["atenção a Pratylenchus brachyurus", "milheto e braquiárias como possíveis hospedeiros", "crotalárias específicas"],
    },
    {
        "title": "Cover plants in second crop: nutrients in straw and cotton yield in succession",
        "organization": "Embrapa Algodão",
        "url": "https://www.embrapa.br/en/busca-de-publicacoes/-/publicacao/1157023/cover-plants-in-second-crop-nutrients-in-straw-and-cotton-yield-in-succession",
        "supports": ["comparação de milheto, Urochloa e crotalárias antes do algodão"],
    },
    {
        "title": "Rotação de culturas",
        "organization": "Embrapa Ageitec",
        "url": "https://www.embrapa.br/web/agencia-de-informacao-tecnologica/tematicas/sistema-plantio-direto/fazendo-certo/planejando-e-executando/fase-de-implantacao/organizando-o-sistema-produtivo/rotacao-de-culturas",
        "supports": ["diversificação de espécies", "intervalo de retorno do algodão"],
    },
]


def get_cerrado_mvp_catalog() -> dict:
    """Retorna o catálogo pequeno do MVP, com fontes e avisos de uso."""
    return {
        "scope": "Cerrado brasileiro — MVP inicial",
        "commercial_crops": COMMERCIAL_CROPS,
        "transition_crops": TRANSITION_CROPS,
        "phase_2_commercial_candidates_not_active": ["sorgo", "girassol"],
        "future_transition_candidates_not_active": ["guandu (Cajanus cajan)", "estilosantes"],
        "sources": SOURCES,
        "important_note": (
            "Não há uma cultura de transição ideal para toda propriedade. A escolha depende de janela de semeadura, "
            "água disponível, solo, manejo, espécie/cultivar e diagnóstico fitossanitário."
        ),
    }


def recommend_transition_options(
    current_crop: str,
    next_crop: str,
    days_available: int,
    pratylenchus_brachyurus_status: str = "unknown",
    objective: str = "balanced",
    cotton_years_since_last: int | None = None,
) -> dict:
    """Gera opções transparentes de plantas de transição para triagem.

    Não calcula produtividade, não afirma controle de pragas e não substitui
    calendário agrícola ou validação regional. Os dias informados são apenas
    uma restrição inicial; a duração de cada espécie ainda precisa ser local.
    """
    valid_crops = set(COMMERCIAL_CROPS)
    if current_crop not in valid_crops or next_crop not in valid_crops:
        raise ValueError("current_crop e next_crop devem ser soybean, maize ou cotton.")
    if days_available < 0:
        raise ValueError("days_available não pode ser negativo.")
    if pratylenchus_brachyurus_status not in {"present", "not_detected", "unknown"}:
        raise ValueError("pratylenchus_brachyurus_status deve ser present, not_detected ou unknown.")
    if objective not in {"balanced", "ground_cover", "nitrogen_cycling", "nematode_management"}:
        raise ValueError("Objetivo inválido.")

    warnings: list[str] = []
    cotton_return_warning = None
    if next_crop == "cotton" and cotton_years_since_last is not None and cotton_years_since_last < 2:
        cotton_return_warning = (
            "Atenção: o algodão retornaria à gleba em menos de dois anos. A referência Embrapa consultada "
            "indica intervalo mínimo de dois anos; confirmar a regra técnica e fitossanitária aplicável à região."
        )
        warnings.append(cotton_return_warning)

    if days_available == 0:
        warnings.append("Não há janela informada para semear uma cultura de transição; avaliar manutenção da palhada existente.")
    if current_crop == next_crop:
        warnings.append("A cultura comercial atual e a próxima são iguais; isso é sucessão/continuidade da mesma cultura, não diversificação por rotação.")

    base_order = {
        "balanced": ["urochloa_ruziziensis", "millet", "crotalaria_spectabilis", "crotalaria_ochroleuca"],
        "ground_cover": ["urochloa_ruziziensis", "millet", "crotalaria_spectabilis", "crotalaria_ochroleuca"],
        "nitrogen_cycling": ["crotalaria_spectabilis", "crotalaria_ochroleuca", "urochloa_ruziziensis", "millet"],
        "nematode_management": ["crotalaria_spectabilis", "crotalaria_ochroleuca", "urochloa_ruziziensis", "millet"],
    }[objective]
    # Se P. brachyurus estiver confirmado, opções que podem multiplicá-lo
    # não devem aparecer antes das alternativas específicas de manejo.
    if pratylenchus_brachyurus_status == "present":
        base_order = ["crotalaria_spectabilis", "crotalaria_ochroleuca", "urochloa_ruziziensis", "millet"]

    candidates = []
    for crop_id in base_order:
        crop = TRANSITION_CROPS[crop_id]
        suitability = "candidate_for_local_validation"
        reasons = list(crop["main_functions"])
        cautions = list(crop["fitosanitary_notes"])
        if pratylenchus_brachyurus_status == "present":
            if crop_id in {"millet", "urochloa_ruziziensis"}:
                suitability = "avoid_as_default_when_P_brachyurus_confirmed"
                reasons.append("Não priorizar enquanto P. brachyurus estiver confirmado na área.")
            else:
                suitability = "priority_candidate_with_technical_validation"
                reasons.append("Opção mais coerente com o objetivo de manejo de P. brachyurus nas referências consultadas.")
        elif pratylenchus_brachyurus_status == "unknown" and crop_id in {"millet", "urochloa_ruziziensis"}:
            suitability = "candidate_with_nematode_caution"
            cautions.append("Diagnóstico de nematoides desconhecido: não tratar esta opção como segura para P. brachyurus.")
        if days_available == 0:
            suitability = "not_applicable_no_sowing_window"
        candidates.append({
            "crop_id": crop_id,
            "name_pt": crop["name_pt"],
            "suitability": suitability,
            "reasons": reasons,
            "cautions": cautions,
        })

    if pratylenchus_brachyurus_status == "present":
        warnings.append(
            "As culturas comerciais soja, milho e algodão também podem ser hospedeiras de P. brachyurus. "
            "A rotação não elimina o nematoide; usar análise nematológica e recomendação específica por espécie/cultivar."
        )
    elif pratylenchus_brachyurus_status == "unknown":
        warnings.append("Sem diagnóstico nematológico, o sistema não presume ausência de P. brachyurus nem declara uma cobertura como não hospedeira.")

    warnings.append(
        "A semeadura de plantas de cobertura no Cerrado depende da chuva remanescente: quanto mais tarde na estação chuvosa, "
        "menor tende a ser o estabelecimento e a biomassa. Não há data universal nesta versão."
    )

    return {
        "current_commercial_crop": current_crop,
        "next_commercial_crop": next_crop,
        "days_available_for_transition": days_available,
        "days_available_note": "Informação de triagem; ainda não há duração agronômica parametrizada para cada cultivar e época.",
        "objective": objective,
        "pratylenchus_brachyurus_status": pratylenchus_brachyurus_status,
        "candidates": candidates,
        "cotton_return_warning": cotton_return_warning,
        "warnings": warnings,
        "interpretation": (
            "Lista de triagem, não prescrição agronômica. A ordem é qualitativa e não representa uma pontuação validada "
            "nem substitui avaliação de solo, calendário, água, cultivar e diagnóstico de pragas/nematoides."
        ),
        "implementation_status": "rule_based_mvp_with_regional_evidence_not_field_validated",
    }
