"""Regras demonstrativas de hospedeiros para avaliação de sequências.

Esta base inicial é intencionalmente pequena. Cada relação precisa de fonte,
região e status; ausência de uma cultura na lista NÃO significa não hospedeira.
"""

PEST_HOST_REFERENCES = {
    "fall_armyworm": {
        "scientific_name": "Spodoptera frugiperda",
        "name_pt": "Lagarta-do-cartucho / fall armyworm",
        "organism_type": "insect",
        "geographic_scope": "global pest; host importance varies by region",
        "major_hosts": ["maize", "sorghum", "rice", "soybean", "cotton", "sugarcane"],
        "validated_nonhosts": [],
        "host_source": "EPPO Global Database; host classification indicative and records include more than 350 plant species in the Americas",
        "source_url": "https://gd.eppo.int/taxon/LAPHFR/datasheet",
        "caveat": "Polífaga; plantas espontâneas e outras culturas podem manter populações. Uma cultura fora da lista não deve ser tratada como não hospedeira.",
    },
    "soybean_cyst_nematode": {
        "scientific_name": "Heterodera glycines",
        "name_pt": "Nematoide-de-cisto-da-soja",
        "organism_type": "nematode",
        "geographic_scope": "confirmed fields/regions; host tables below are extension references, chiefly North American",
        "major_hosts": ["soybean", "common_bean", "cowpea"],
        "validated_nonhosts": ["maize", "sorghum", "wheat", "barley", "oat", "rice", "cotton", "sunflower", "rapeseed", "groundnut"],
        "host_source": "University of Minnesota Extension / University of Florida IFAS; confirm cultivar, local weed hosts and local nematode population",
        "source_url": "https://extension.umn.edu/agriculture/crop-production/soybean/soybean-cyst-nematode-management-guide",
        "caveat": "Não extrapolar sem diagnóstico laboratorial nem assumir que status de hospedeiro é idêntico em todos os países/isolados. Cistos podem persistir por anos e plantas daninhas também hospedam.",
    },
}


def assess_rotation_sequence(crop_sequence: list[str], detected_pests: list[str] | None = None) -> dict:
    """Avalia sequência por relações documentadas; não prediz infestação nem dano."""
    if len(crop_sequence) < 2:
        raise ValueError("A sequência deve conter ao menos duas culturas.")
    pests = detected_pests or list(PEST_HOST_REFERENCES.keys())
    transitions = []
    for index, (previous, following) in enumerate(zip(crop_sequence, crop_sequence[1:]), start=1):
        transition = {"from": previous, "to": following, "transition_number": index, "pests": []}
        for pest_id in pests:
            pest = PEST_HOST_REFERENCES.get(pest_id)
            if pest is None:
                transition["pests"].append({"pest_id": pest_id, "status": "no_reference_record", "interpretation": "Sem base documentada suficiente no catálogo."})
                continue
            prev_host = previous in pest["major_hosts"]
            next_host = following in pest["major_hosts"]
            next_nonhost = following in pest["validated_nonhosts"]
            if prev_host and next_host:
                status = "host_to_host"
                message = "A cultura seguinte também consta como hospedeira; a troca não representa quebra deste hospedeiro." 
            elif prev_host and next_nonhost:
                status = "potential_host_break"
                message = "A cultura seguinte consta como não hospedeira na referência consultada; isso pode interromper a multiplicação no cultivo, mas não elimina o organismo nem hospedeiros espontâneos."
            elif (not prev_host) and next_host:
                status = "host_introduction"
                message = "A cultura seguinte consta como hospedeira; se o organismo estiver presente, esta mudança pode introduzir um hospedeiro na sequência."
            else:
                status = "unknown_or_not_directly_supported"
                message = "A relação não permite afirmar quebra nem continuidade; verificar espécie, cultivar, região e hospedeiros alternativos."
            transition["pests"].append({
                "pest_id": pest_id,
                "scientific_name": pest["scientific_name"],
                "status": status,
                "interpretation": message,
                "geographic_scope": pest["geographic_scope"],
                "source_url": pest["source_url"],
                "caveat": pest["caveat"],
            })
        transitions.append(transition)
    return {
        "crop_sequence": crop_sequence,
        "transitions": transitions,
        "overall_note": "Não é uma previsão de pressão de praga. Para recomendação local, adicionar presença confirmada, abundância, cultivar/resistência, hospedeiros espontâneos, práticas de manejo e dados fitossanitários regionais.",
        "data_completeness": "starter_rules_only",
    }
