# Fórmulas matemáticas do CerradoShift em funções Python

Este documento acompanha `app/core/math_formulas.py`, um módulo com as equações reunidas em funções reutilizáveis.

## 1. Como usar

O módulo usa apenas a biblioteca padrão do Python; não exige instalar NumPy ou Pandas.

Na pasta `cerradoshift_api`, execute:

```bash
python -m examples.formulas_quickstart
```

Para usar dentro de outro arquivo Python:

```python
from app.core.math_formulas import (
    fao56_et0_mm_day,
    crop_evapotranspiration_potential_mm_day,
    total_available_water_mm,
    readily_available_water_mm,
    water_stress_coefficient,
    daily_water_balance_step,
)
```

## 2. Ordem típica de cálculo

1. **Clima:** `mean_air_temperature_c`, `saturation_vapour_pressure_kpa`, `actual_vapour_pressure_kpa`, `slope_vapour_pressure_curve_kpa_c`, `atmospheric_pressure_kpa`, `extraterrestrial_radiation_mj_m2_day`, `net_radiation_fao56_mj_m2_day`.
2. **Demanda atmosférica:** `fao56_et0_mm_day`.
3. **Cultura:** `crop_stage_and_kc`, `root_depth_linear_m`, `daily_gdd_c_day`, `adjusted_depletion_fraction`.
4. **Demanda da cultura e reserva de água:** `crop_evapotranspiration_potential_mm_day`, `total_available_water_mm`, `readily_available_water_mm`, `water_stress_coefficient`.
5. **Entradas e saídas diárias:** `scs_curve_number_runoff_mm`, `effective_rainfall_mm`, `net_irrigation_mm`, `daily_water_balance_step`.
6. **Indicadores satelitais:** `vegetation_indices`, `summarize_vegetation_pixels`, `standardized_anomaly`.
7. **Solo e erosão:** `rusle_ls_factor`, `rusle_soil_loss_t_ha_year`.
8. **Modelos complementares:** funções de Kc dual, resposta da produtividade à água e relação hospedeiro–cultura.
9. **Comparação multicritério:** `weighted_rotation_score` é apenas um esqueleto experimental, ainda sem pesos ou indicadores validados para o Cerrado.

## 3. Catálogo de funções

### Clima e ET0

- `mean_air_temperature_c`: média de Tmax e Tmin.
- `saturation_vapour_pressure_kpa`: pressão de vapor de saturação.
- `mean_saturation_vapour_pressure_kpa`: média de es(Tmax) e es(Tmin).
- `actual_vapour_pressure_kpa`: pressão real, preferindo ponto de orvalho; UR média é uma aproximação.
- `vapour_pressure_deficit_kpa`: déficit de pressão de vapor.
- `slope_vapour_pressure_curve_kpa_c`: inclinação Δ da curva de vapor.
- `atmospheric_pressure_kpa` e `psychrometric_constant_kpa_c`: pressão atmosférica por altitude e constante psicrométrica.
- `extraterrestrial_radiation_mj_m2_day` e `daylight_hours`: geometria solar diária.
- `wind_10m_to_2m`: conversão de altura do vento quando necessária. Não reaplique se a fonte já fornecer vento a 2 m.
- `net_radiation_fao56_mj_m2_day`: saldo de ondas curtas/longas e radiação líquida.
- `fao56_et0_mm_day`: Penman–Monteith FAO-56 diário. Assume G=0 para passo diário.

### Cultura e fenologia

- `crop_stage_and_kc`: estágio e Kc por interpolação em quatro fases.
- `root_depth_linear_m`: aproximação linear de crescimento radicular.
- `adjusted_depletion_fraction`: ajuste da fração p em função de ETc.
- `daily_gdd_c_day` e `cumulative_gdd_c_day`: graus-dia diários e acumulados.
- `daily_heat_excess_c` e `summarize_heat_exposure`: excesso diário e contagem/soma de dias acima de um limiar.

### Água e irrigação

- `total_available_water_mm`: TAW = 1000(θFC − θWP)Zr.
- `readily_available_water_mm`: RAW = p × TAW.
- `water_stress_coefficient`: Ks FAO-56 em função da depleção.
- `scs_curve_number_runoff_mm`: escoamento por Curve Number.
- `effective_rainfall_mm`: precipitação menos escoamento estimado/observado.
- `net_irrigation_mm` e `irrigation_application_loss_mm`: lâmina líquida e perda de aplicação.
- `irrigation_volume_m3`: converte lâmina e área em volume.
- `initial_depletion_mm`: depleção inicial a partir de umidade medida ou fração assumida.
- `expand_root_zone_depletion_mm`: adiciona a contribuição da nova camada alcançada pelas raízes.
- `daily_water_balance_step`: um passo diário simplificado de armazenamento, chuva, irrigação, ETa e drenagem.
- `irrigation_recommendation_mm`: regra provisória de reposição até metade do RAW.
- `longest_dry_spell_days`: maior sequência de dias abaixo de um limiar de chuva.
- `count_water_stress_days`: conta os dias em que Ks fica abaixo de um limite configurado.

### Sensoriamento remoto

- `vegetation_indices`: NDVI, EVI, SAVI, MSAVI2, NDMI, NDWI Green–NIR, NBR e NBR2.
- `summarize_vegetation_pixels`: médias/medianas e fração válida dos pixels.
- `standardized_anomaly`: Z-score em relação a estatísticas históricas.

As bandas devem ser reflectância de superfície escalada, normalmente 0–1, depois de máscara de nuvens/sombras e QA. O código não baixa nem corrige imagens por conta própria.

### Erosão e modelos complementares

- `rusle_ls_factor`: fator topográfico LS simplificado.
- `rusle_soil_loss_t_ha_year`: A = R × K × LS × C × P.
- `evaporation_reduction_coefficient_kr`: Kr do método dual.
- `maximum_crop_coefficient_kcmax`: Kc máximo do método dual.
- `soil_evaporation_coefficient_ke`: Ke do método dual.
- `dual_kc_evapotranspiration_mm_day`: separa transpiração e evaporação do solo.
- `fao_water_yield_response`: relação de resposta relativa da produtividade à água usando Ky.
- `classify_host_transition`: regra lógica de continuidade/quebra potencial de hospedeiro.
- `weighted_rotation_score`: soma ponderada experimental de indicadores de rotação normalizados.

## 4. Exemplo encadeado

`examples/formulas_quickstart.py` demonstra este encadeamento com números fictícios:

```python
et0 = fao56_et0_mm_day(...)
etc = crop_evapotranspiration_potential_mm_day(kc=1.10, et0_mm_day=et0)
taw = total_available_water_mm(field_capacity=0.30, wilting_point=0.15, root_depth_m=0.60)
raw = readily_available_water_mm(p_fraction=0.50, taw_mm=taw)
ks = water_stress_coefficient(depletion_mm=35, taw_mm=taw, raw_mm=raw)
resultado = daily_water_balance_step(
    depletion_start_mm=35,
    taw_mm=taw,
    raw_mm=raw,
    etc_potential_mm=etc,
    precipitation_mm=0,
)
```

Os valores de exemplo são apenas didáticos. Não representam recomendação para uma lavoura real.

## 5. O que não está implementado como modelo matemático validado

Este módulo não cria fórmulas que ainda não foram especificadas/calibradas. Continuam pendentes:

- balanços de N, P e K e mineralização/ciclagem de nutrientes;
- carbono orgânico e dinâmica da matéria orgânica;
- modelo de biomassa e produção de palhada calibrado para culturas/cultivares;
- conversão validada de NDVI/EVI em Kc, biomassa ou fator C da RUSLE;
- previsão fenológica por GDD/fotoperíodo conectada automaticamente ao Kc;
- modelos epidemiológicos e de população de nematoides por espécie/cultivar;
- produtividade absoluta em t/ha;
- otimizador de rotações com restrições agronômicas, calendário e economia.

`weighted_rotation_score` é uma estrutura experimental: não deve ser usada para recomendar rotações até que indicadores, normalizações, pesos e restrições tenham sido definidos e validados por agrônomos.

## 6. Cuidados de interpretação

- ET0 é demanda atmosférica de referência, não consumo medido da cultura.
- Kc, p, raízes, GDD e Ky precisam ser específicos para cultura, cultivar, fase, época e sistema de manejo.
- A umidade SMAP superficial não é igual à água disponível em toda a zona radicular.
- NDVI/EVI são indicadores espectrais; não diagnosticam sozinhos pragas, doenças ou deficiência nutricional.
- RUSLE exige R, K, C e P com método e unidades compatíveis; não estime R apenas pela soma da chuva diária.
- A aplicação diária de Curve Number é uma aproximação; o método é originalmente baseado em eventos de chuva.
- O passo diário usa um reservatório simplificado e não representa fluxo capilar, redistribuição completa em camadas ou lençol freático.
- Não some o ETc do método Kc simples ao ETc dual: isso duplicaria fluxos de água.
- Não transforme pontuações experimentais em recomendação agronômica sem validação de campo.

## 7. Testes

A suíte inclui `tests/test_math_formulas.py`. Na pasta do projeto, execute:

```bash
python -m pytest -q
```

Os testes verificam cálculo e validação das funções; não substituem calibração ou validação agronômica em lavouras reais.
