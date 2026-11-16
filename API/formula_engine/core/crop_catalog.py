"""Valores bibliográficos de referência; não são prescrições para o Cerrado.

As durações fenológicas e a profundidade radicular efetiva precisam ser
configuradas por cultivar, época de plantio, solo e manejo da região.
"""

CROP_REFERENCE_CATALOG = {
    "soybean": {
        "label": "Soja",
        "profile_status": "reference_values_only",
        "reference_parameters": {
            "kc_initial": 0.40,
            "kc_mid": 1.15,
            "kc_end": 0.50,
            "depletion_fraction_p": 0.50,
            "maximum_root_depth_range_m": [0.60, 1.30],
        },
        "required_local_parameters": [
            "cultivar", "stage_initial_days", "stage_development_days",
            "stage_mid_days", "stage_late_days", "root_depth_initial_m",
            "root_depth_max_m dentro da faixa/solo efetivo", "root_growth_days",
            "base_temperature_c", "heat_thresholds_by_stage",
        ],
        "source": "FAO-56 Tables 12 and 22; generic reference conditions",
        "caveat": "Kc representa cultura bem manejada, não estressada, em clima subúmido de referência. Ajustar para clima, cultivar, população, irrigação e frequência de molhamento.",
    },
    "field_maize": {
        "label": "Milho-grão",
        "profile_status": "reference_values_only",
        "reference_parameters": {
            "kc_initial": 0.30,
            "kc_mid": 1.20,
            "kc_end_options": [0.60, 0.35],
            "depletion_fraction_p": 0.55,
            "maximum_root_depth_range_m": [1.00, 1.70],
        },
        "required_local_parameters": [
            "cultivar/híbrido", "estágio e duração de cada fase", "root_depth_initial_m",
            "root_depth_max_m limitado ao solo efetivo", "root_growth_days",
            "kc_end conforme umidade na colheita", "base_temperature_c",
            "heat_thresholds_by_stage",
        ],
        "source": "FAO-56 Tables 12 and 22; generic field maize reference",
        "caveat": "Kc_end depende do ponto de colheita (grão úmido versus secagem em campo); ajustar durações, clima e cultivar.",
    },
    "brachiaria": {
        "label": "Braquiária",
        "profile_status": "local_profile_required",
        "reference_parameters": None,
        "required_local_parameters": [
            "espécie/cultivar (ex.: Urochloa brizantha, U. ruziziensis)",
            "uso (pastejo, cobertura, palhada ou produção de sementes)",
            "curva Kc ou Kcb por manejo", "estágios/cortes/pastejo",
            "profundidade radicular e fração p com fonte local",
        ],
        "source": "Preencher com publicação/ensaio Embrapa ou literatura específica da espécie e manejo",
        "caveat": "Não reutilizar automaticamente parâmetros de pastagem genérica para uma espécie de Brachiaria/Urochloa.",
    },
}
