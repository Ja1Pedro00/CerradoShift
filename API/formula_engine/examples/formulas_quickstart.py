"""Exemplo simples de como chamar as fórmulas matemáticas do CerradoShift."""
from app.core.math_formulas import (
    fao56_et0_mm_day,
    crop_evapotranspiration_potential_mm_day,
    total_available_water_mm,
    readily_available_water_mm,
    water_stress_coefficient,
    daily_water_balance_step,
    vegetation_indices,
)

# 1) Clima: valores fictícios de um dia para demonstrar o uso.
et0 = fao56_et0_mm_day(
    tmax_c=30.0,
    tmin_c=20.0,
    rh_mean_pct=65.0,
    wind_2m_m_s=2.0,
    solar_radiation_mj_m2_day=18.0,
    latitude_deg=-16.0,
    elevation_m=800.0,
    day_of_year=320,
)

# 2) Cultura: exemplo de Kc. Em produção, o Kc virá do perfil validado da cultura.
kc = 1.10
etc_potencial = crop_evapotranspiration_potential_mm_day(kc, et0)

# 3) Solo: valores ilustrativos de capacidade de campo, ponto de murcha e raízes.
taw = total_available_water_mm(field_capacity=0.30, wilting_point=0.15, root_depth_m=0.60)
raw = readily_available_water_mm(p_fraction=0.50, taw_mm=taw)
ks = water_stress_coefficient(depletion_mm=35.0, taw_mm=taw, raw_mm=raw)

# 4) Um dia de balanço hídrico. Sem chuva e sem irrigação neste exemplo.
balanco = daily_water_balance_step(
    depletion_start_mm=35.0,
    taw_mm=taw,
    raw_mm=raw,
    etc_potential_mm=etc_potencial,
    precipitation_mm=0.0,
    irrigation_gross_mm=0.0,
    irrigation_efficiency=0.85,
)

# 5) Índices: reflectâncias fictícias, já corrigidas e em escala 0–1.
indices = vegetation_indices(
    red=0.10,
    nir=0.60,
    blue=0.05,
    green=0.20,
    swir1=0.30,
    swir2=0.25,
)

print("ET0 (mm/dia):", round(et0, 3))
print("ETc potencial (mm/dia):", round(etc_potencial, 3))
print("TAW (mm):", round(taw, 2), "RAW (mm):", round(raw, 2), "Ks:", round(ks, 3))
print("Balanço diário:", balanco)
print("Índices espectrais:", indices)
