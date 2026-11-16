"""Exemplos iniciais de problemas fitossanitários por cultura.

Não é uma lista exaustiva nem um mapa global de ocorrência. A ocorrência e
importância devem ser filtradas por país, região, ambiente, cultivar e época.
"""

CROP_HEALTH_STARTER_CATALOG = {
    "maize": {
        "problems": [
            {"scientific_name": "Spodoptera frugiperda", "common_name": "lagarta-do-cartucho / fall armyworm", "type": "insect", "note": "polífaga; milho e outras culturas são hospedeiras"},
            {"scientific_name": "Ostrinia nubilalis", "common_name": "broca-europeia-do-milho", "type": "insect", "note": "importância regional, especialmente em zonas temperadas"},
            {"scientific_name": "Dalbulus maidis", "common_name": "cigarrinha-do-milho", "type": "insect_vector", "note": "mais relevante em regiões onde ocorrem enfezamentos associados"},
        ],
        "sources": ["https://gd.eppo.int/taxon/LAPHFR/datasheet"],
    },
    "soybean": {
        "problems": [
            {"scientific_name": "Heterodera glycines", "common_name": "nematoide-de-cisto-da-soja", "type": "nematode", "note": "ocorrência concentrada em regiões produtoras; diagnóstico do solo é essencial"},
            {"scientific_name": "Phakopsora pachyrhizi", "common_name": "ferrugem-asiática-da-soja", "type": "fungus", "note": "importância varia com região, clima e calendário"},
            {"scientific_name": "Aphis glycines", "common_name": "pulgão-da-soja", "type": "insect", "note": "notável em partes da Ásia e América do Norte; distribuição regional"},
        ],
        "sources": ["https://extension.umn.edu/agriculture/crop-production/soybean/soybean-cyst-nematode-management-guide", "https://gd.eppo.int/taxon/LAPHFR/datasheet"],
    },
    "wheat": {
        "problems": [
            {"scientific_name": "Puccinia striiformis f. sp. tritici", "common_name": "ferrugem-amarela", "type": "fungus", "note": "doença de distribuição ampla em países produtores de trigo"},
            {"scientific_name": "Puccinia triticina", "common_name": "ferrugem-da-folha", "type": "fungus", "note": "raças e importância variam regionalmente"},
            {"scientific_name": "Puccinia graminis f. sp. tritici", "common_name": "ferrugem-do-colmo", "type": "fungus", "note": "monitorar raças e hospedeiros alternativos"},
        ],
        "sources": ["https://www.fao.org/pest-and-pesticide-management/ipm/wheat-rust/en/"],
    },
    "rice": {
        "problems": [
            {"scientific_name": "Magnaporthe oryzae" , "common_name": "brusone do arroz", "type": "fungus", "note": "doença importante; ambiente e cultivar influenciam epidemias"},
            {"scientific_name": "Nilaparvata lugens", "common_name": "cigarrinha-marrom / brown planthopper", "type": "insect", "note": "relevante em partes da Ásia; ocorrência varia por região"},
            {"scientific_name": "Xanthomonas oryzae pv. oryzae", "common_name": "queima bacteriana das folhas", "type": "bacterium", "note": "doença bacteriana importante em sistemas de arroz"},
        ],
        "sources": ["https://rice-diseases.irri.org/", "https://niphm.gov.in/IPMPackages/Rice.pdf"],
    },
    "cotton": {
        "problems": [
            {"scientific_name": "Anthonomus grandis", "common_name": "bicudo-do-algodoeiro", "type": "insect", "note": "distribuição/regulação variam; há programas de erradicação e zonas livres"},
            {"scientific_name": "Pectinophora gossypiella", "common_name": "lagarta-rosada", "type": "insect", "note": "ausente de algumas regiões após programas de erradicação"},
            {"scientific_name": "Bemisia tabaci", "common_name": "mosca-branca", "type": "insect_vector", "note": "complexo de espécies/biotipos e vetores; manejo local necessário"},
        ],
        "sources": ["https://www.aphis.usda.gov/plant-pests-diseases/cotton-pests"],
    },
    "sorghum": {
        "problems": [
            {"scientific_name": "Atherigona soccata", "common_name": "mosca-da-plântula / sorghum shoot fly", "type": "insect", "note": "importância em regiões da Ásia, África e Mediterrâneo"},
            {"scientific_name": "Stenodiplosis sorghicola", "common_name": "mosquito-do-sorgo", "type": "insect", "note": "praga de panículas em diferentes continentes"},
            {"scientific_name": "Spodoptera frugiperda", "common_name": "lagarta-do-cartucho", "type": "insect", "note": "sorgo também pode ser hospedeiro"},
        ],
        "sources": ["https://oar.icrisat.org/2225/"],
    },
    "common_bean": {
        "problems": [
            {"scientific_name": "Colletotrichum lindemuthianum", "common_name": "antracnose do feijoeiro", "type": "fungus", "note": "raças e severidade variam com clima e cultivar"},
            {"scientific_name": "Pseudocercospora griseola", "common_name": "mancha-angular", "type": "fungus", "note": "importante em regiões tropicais e subtropicais"},
            {"scientific_name": "Ophiomyia phaseoli", "common_name": "mosca-da-haste / bean fly", "type": "insect", "note": "ocorrência e espécie variam conforme região"},
        ],
        "sources": ["https://www.accessagriculture.org/sites/default/files/2025-12/FiBL%20African%20Organic%20Agriculture%20-%20Beans.pdf"],
    },
    "potato": {
        "problems": [
            {"scientific_name": "Phytophthora infestans", "common_name": "requeima / late blight", "type": "oomycete", "note": "doença amplamente importante em batata"},
            {"scientific_name": "Leptinotarsa decemlineata", "common_name": "besouro-do-colorado", "type": "insect", "note": "distribuição regional; praga séria em zonas onde está estabelecida"},
            {"scientific_name": "Globodera rostochiensis", "common_name": "nematoide-dourado da batata", "type": "nematode", "note": "praga de solo com importância regulatória em várias regiões"},
        ],
        "sources": ["https://cipotato.org/potato/potato-pests-diseases/"],
    },
    "cassava": {
        "problems": [
            {"scientific_name": "Cassava mosaic begomoviruses", "common_name": "complexo do mosaico da mandioca", "type": "virus", "note": "transmitidos por mosca-branca e material de plantio"},
            {"scientific_name": "Cassava brown streak viruses", "common_name": "complexo da estria-marrom da mandioca", "type": "virus", "note": "especialmente importante em partes da África Oriental"},
            {"scientific_name": "Phenacoccus manihoti", "common_name": "cochonilha-da-mandioca", "type": "insect", "note": "importância em partes da África e Ásia"},
        ],
        "sources": ["https://www.fao.org/agriculture/crops/thematic-sitemap/theme/pests/cassava-diseases/cassava-related-diseases/en/", "https://www-pub.iaea.org/MTCD/Publications/PDF/TE1840_web.pdf"],
    },
    "citrus": {
        "problems": [
            {"scientific_name": "Candidatus Liberibacter asiaticus", "common_name": "huanglongbing / greening dos citros", "type": "bacterium", "note": "associada a vetores; doença com enorme importância fitossanitária"},
            {"scientific_name": "Diaphorina citri", "common_name": "psilídeo-asiático-dos-citros", "type": "insect_vector", "note": "vetor associado ao HLB em várias regiões"},
            {"scientific_name": "Xanthomonas citri subsp. citri", "common_name": "cancro cítrico", "type": "bacterium", "note": "distribuição e exigências regulatórias dependem do país"},
        ],
        "sources": ["https://www.aphis.usda.gov/plant-pests-diseases/citrus-diseases"],
    },
    "coffee": {
        "problems": [
            {"scientific_name": "Hypothenemus hampei", "common_name": "broca-do-café", "type": "insect", "note": "praga de distribuição ampla em regiões produtoras"},
            {"scientific_name": "Hemileia vastatrix", "common_name": "ferrugem-do-cafeeiro", "type": "fungus", "note": "ambiente, altitude, cultivar e manejo influenciam risco"},
        ],
        "sources": ["https://www.ippc.int/en/resources/publications/top-crops-why-protecting-them-from-plant-pests-matter/coffee/"],
    },
    "banana": {
        "problems": [
            {"scientific_name": "Pseudocercospora fijiensis", "common_name": "sigatoka-negra", "type": "fungus", "note": "presente em muitas zonas produtoras"},
            {"scientific_name": "Fusarium oxysporum f. sp. cubense Tropical Race 4", "common_name": "murcha de Fusarium TR4", "type": "fungus", "note": "patógeno de solo; risco depende da presença local e biossegurança"},
        ],
        "sources": ["https://www.atermaisdigital.cnptia.embrapa.br/web/banana/doencas", "https://unctad.org/system/files/official-document/INFOCOMM_cp01_Banana_en.pdf"],
    },
}

for _record in CROP_HEALTH_STARTER_CATALOG.values():
    _record["coverage_status"] = "illustrative_not_exhaustive"
    _record["warning"] = "Ocorrência, importância e status de quarentena dependem do país/região. Não usar esta lista como diagnóstico ou prescrição." 
