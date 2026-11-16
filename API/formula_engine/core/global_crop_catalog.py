"""Catálogo taxonômico global inicial; não contém coeficientes agronômicos universais.

Os perfis de Kc, fenologia, profundidade radicular e limites térmicos devem ser
acrescentados somente quando houver fonte/cultivar/sistema de cultivo explícitos.
"""

GLOBAL_CROP_CATALOG = {
    # Cereais e gramíneas comerciais
    "maize": {"name_pt": "Milho", "scientific_name": "Zea mays", "family": "Poaceae", "functional_group": "cereal", "life_cycle": "annual", "uses": ["grain", "silage", "cover_or_fodder"]},
    "rice": {"name_pt": "Arroz", "scientific_name": "Oryza sativa", "family": "Poaceae", "functional_group": "cereal", "life_cycle": "annual", "uses": ["grain"], "production_systems": ["upland", "irrigated", "rainfed_lowland"]},
    "wheat": {"name_pt": "Trigo", "scientific_name": "Triticum aestivum", "family": "Poaceae", "functional_group": "cereal", "life_cycle": "annual", "uses": ["grain"]},
    "barley": {"name_pt": "Cevada", "scientific_name": "Hordeum vulgare", "family": "Poaceae", "functional_group": "cereal", "life_cycle": "annual", "uses": ["grain", "forage"]},
    "sorghum": {"name_pt": "Sorgo", "scientific_name": "Sorghum bicolor", "family": "Poaceae", "functional_group": "cereal", "life_cycle": "annual", "uses": ["grain", "forage", "silage"]},
    "millet": {"name_pt": "Milheto / painço (grupo; especificar espécie)", "scientific_name": "Pennisetum glaucum / Setaria italica (examples)", "family": "Poaceae", "functional_group": "cereal_or_cover", "life_cycle": "annual", "uses": ["grain", "forage", "cover"]},
    "oat": {"name_pt": "Aveia", "scientific_name": "Avena sativa", "family": "Poaceae", "functional_group": "cereal", "life_cycle": "annual", "uses": ["grain", "forage", "cover"]},
    "rye": {"name_pt": "Centeio", "scientific_name": "Secale cereale", "family": "Poaceae", "functional_group": "cereal", "life_cycle": "annual", "uses": ["grain", "cover"]},
    "sugarcane": {"name_pt": "Cana-de-açúcar", "scientific_name": "Saccharum officinarum", "family": "Poaceae", "functional_group": "sugar_crop", "life_cycle": "perennial_or_ratooned", "uses": ["sugar", "bioenergy"]},
    # Leguminosas / Fabaceae
    "soybean": {"name_pt": "Soja", "scientific_name": "Glycine max", "family": "Fabaceae", "functional_group": "legume_oilseed", "life_cycle": "annual", "uses": ["grain", "oil", "protein"]},
    "common_bean": {"name_pt": "Feijão-comum", "scientific_name": "Phaseolus vulgaris", "family": "Fabaceae", "functional_group": "pulse", "life_cycle": "annual", "uses": ["grain"]},
    "cowpea": {"name_pt": "Feijão-caupi", "scientific_name": "Vigna unguiculata", "family": "Fabaceae", "functional_group": "pulse", "life_cycle": "annual", "uses": ["grain", "forage"]},
    "chickpea": {"name_pt": "Grão-de-bico", "scientific_name": "Cicer arietinum", "family": "Fabaceae", "functional_group": "pulse", "life_cycle": "annual", "uses": ["grain"]},
    "lentil": {"name_pt": "Lentilha", "scientific_name": "Lens culinaris", "family": "Fabaceae", "functional_group": "pulse", "life_cycle": "annual", "uses": ["grain"]},
    "pea": {"name_pt": "Ervilha", "scientific_name": "Pisum sativum", "family": "Fabaceae", "functional_group": "pulse", "life_cycle": "annual", "uses": ["grain", "cover"]},
    "groundnut": {"name_pt": "Amendoim", "scientific_name": "Arachis hypogaea", "family": "Fabaceae", "functional_group": "oilseed_legume", "life_cycle": "annual", "uses": ["grain", "oil"]},
    "pigeon_pea": {"name_pt": "Guandu", "scientific_name": "Cajanus cajan", "family": "Fabaceae", "functional_group": "cover_legume", "life_cycle": "annual_or_perennial", "uses": ["cover", "forage", "grain"]},
    # Óleos, fibras e raízes
    "rapeseed": {"name_pt": "Canola / colza", "scientific_name": "Brassica napus", "family": "Brassicaceae", "functional_group": "oilseed", "life_cycle": "annual", "uses": ["oil"]},
    "sunflower": {"name_pt": "Girassol", "scientific_name": "Helianthus annuus", "family": "Asteraceae", "functional_group": "oilseed", "life_cycle": "annual", "uses": ["oil", "grain"]},
    "cotton": {"name_pt": "Algodão", "scientific_name": "Gossypium hirsutum", "family": "Malvaceae", "functional_group": "fiber_crop", "life_cycle": "annual_or_perennial", "uses": ["fiber", "oilseed_byproduct"]},
    "potato": {"name_pt": "Batata", "scientific_name": "Solanum tuberosum", "family": "Solanaceae", "functional_group": "tuber", "life_cycle": "annual", "uses": ["food"]},
    "cassava": {"name_pt": "Mandioca", "scientific_name": "Manihot esculenta", "family": "Euphorbiaceae", "functional_group": "root_crop", "life_cycle": "perennial_or_harvested_annual", "uses": ["food", "starch"]},
    "sweet_potato": {"name_pt": "Batata-doce", "scientific_name": "Ipomoea batatas", "family": "Convolvulaceae", "functional_group": "root_crop", "life_cycle": "annual", "uses": ["food"]},
    "sugar_beet": {"name_pt": "Beterraba açucareira", "scientific_name": "Beta vulgaris", "family": "Amaranthaceae", "functional_group": "sugar_crop", "life_cycle": "biennial_grown_as_annual", "uses": ["sugar"]},
    # Culturas perenes e tropicais
    "coffee": {"name_pt": "Café", "scientific_name": "Coffea spp.", "family": "Rubiaceae", "functional_group": "beverage_perennial", "life_cycle": "perennial", "uses": ["beverage"]},
    "cocoa": {"name_pt": "Cacau", "scientific_name": "Theobroma cacao", "family": "Malvaceae", "functional_group": "beverage_perennial", "life_cycle": "perennial", "uses": ["food"]},
    "banana": {"name_pt": "Banana", "scientific_name": "Musa spp.", "family": "Musaceae", "functional_group": "fruit_perennial", "life_cycle": "perennial", "uses": ["food"]},
    "citrus": {"name_pt": "Citros", "scientific_name": "Citrus spp.", "family": "Rutaceae", "functional_group": "fruit_perennial", "life_cycle": "perennial", "uses": ["fruit"]},
    "grape": {"name_pt": "Uva", "scientific_name": "Vitis vinifera", "family": "Vitaceae", "functional_group": "fruit_perennial", "life_cycle": "perennial", "uses": ["fruit", "wine"]},
    "olive": {"name_pt": "Oliveira", "scientific_name": "Olea europaea", "family": "Oleaceae", "functional_group": "oil_perennial", "life_cycle": "perennial", "uses": ["oil", "fruit"]},
    "oil_palm": {"name_pt": "Dendê / palma de óleo", "scientific_name": "Elaeis guineensis", "family": "Arecaceae", "functional_group": "oil_perennial", "life_cycle": "perennial", "uses": ["oil"]},
    # Coberturas / adubação verde: espécies, não coeficientes universais
    "sunn_hemp": {"name_pt": "Crotalária-júncea", "scientific_name": "Crotalaria juncea", "family": "Fabaceae", "functional_group": "cover_legume", "life_cycle": "annual", "uses": ["cover", "green_manure"]},
    "showy_crotalaria": {"name_pt": "Crotalária-espectábilis", "scientific_name": "Crotalaria spectabilis", "family": "Fabaceae", "functional_group": "cover_legume", "life_cycle": "annual", "uses": ["cover", "green_manure"]},
    "brachiaria_ruziziensis": {"name_pt": "Urochloa ruziziensis", "scientific_name": "Urochloa ruziziensis", "family": "Poaceae", "functional_group": "cover_grass", "life_cycle": "annual_or_perennial", "uses": ["cover", "forage"]},
    "brachiaria_brizantha": {"name_pt": "Urochloa brizantha", "scientific_name": "Urochloa brizantha", "family": "Poaceae", "functional_group": "cover_grass", "life_cycle": "perennial", "uses": ["cover", "forage"]},
    "mucuna": {"name_pt": "Mucuna-preta", "scientific_name": "Mucuna pruriens", "family": "Fabaceae", "functional_group": "cover_legume", "life_cycle": "annual", "uses": ["cover", "green_manure"]},
    "stylosanthes": {"name_pt": "Estilosantes", "scientific_name": "Stylosanthes spp.", "family": "Fabaceae", "functional_group": "cover_legume", "life_cycle": "perennial_or_annual", "uses": ["cover", "forage"]},
    "alfalfa": {"name_pt": "Alfafa", "scientific_name": "Medicago sativa", "family": "Fabaceae", "functional_group": "forage_legume", "life_cycle": "perennial", "uses": ["forage", "cover"]},
    "red_clover": {"name_pt": "Trevo-vermelho", "scientific_name": "Trifolium pratense", "family": "Fabaceae", "functional_group": "cover_legume", "life_cycle": "perennial_or_annual", "uses": ["cover", "forage"]},
    "hairy_vetch": {"name_pt": "Ervilhaca-peluda", "scientific_name": "Vicia villosa", "family": "Fabaceae", "functional_group": "cover_legume", "life_cycle": "annual", "uses": ["cover", "green_manure"]},
    "phacelia": {"name_pt": "Facélia", "scientific_name": "Phacelia tanacetifolia", "family": "Boraginaceae", "functional_group": "cover_broadleaf", "life_cycle": "annual", "uses": ["cover", "pollinator_resource"]},
    "white_mustard": {"name_pt": "Mostarda-branca", "scientific_name": "Sinapis alba", "family": "Brassicaceae", "functional_group": "cover_brassica", "life_cycle": "annual", "uses": ["cover", "biofumigation_potential"]},
    "forage_radish": {"name_pt": "Nabo-forrageiro", "scientific_name": "Raphanus sativus var. longipinnatus", "family": "Brassicaceae", "functional_group": "cover_brassica", "life_cycle": "annual", "uses": ["cover", "soil_structuring"]},
    "ryegrass": {"name_pt": "Azevém", "scientific_name": "Lolium multiflorum", "family": "Poaceae", "functional_group": "cover_grass", "life_cycle": "annual", "uses": ["cover", "forage"]},
}

for _crop in GLOBAL_CROP_CATALOG.values():
    _crop["agronomic_parameter_status"] = "not_yet_parameterized"
    _crop["note"] = "Cadastro taxonômico e funcional; não presumir Kc, duração, raiz, temperatura ou pH sem fonte local/cultivar."
