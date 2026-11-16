/**
 * Preferências e dados de configuração do CerradoShift.
 * Nesta versão os dados ficam no navegador (localStorage), seguindo o padrão
 * de persistência já utilizado para os talhões e estratégias.
 */
export const PRODUCER_SETTINGS_KEY = "cerradoshift_configuracoes_v1";
export const FIELDS_STORAGE_KEY = "cerradoshift_talhoes";

export const DEFAULT_PREFERENCES = {
  priorities: ["water_saving", "soil_cover", "pest_break"],
  objective: "balanced",
  avoided_transition_crops: [],
  risk_tolerance: "medium",
  notes: "",
};

export function createEmptyFieldProfile() {
  return {
    current_commercial_crop: "",
    crop_stage: "",
    rotation: {
      current_crop: "",
      next_crop: "",
      days_available: "",
      pratylenchus_brachyurus_status: "unknown",
    },
    field: {
      area_ha: "",
      slope_percent: "",
      irrigation_system: "unknown",
      irrigation_efficiency_pct: "",
      water_limited: false,
      available_machinery: [],
      budget_level: "unknown",
      cotton_years_since_last: "",
    },
    soil_test: {
      sample_date: "",
      laboratory: "",
      ph_value: "",
      ph_method: "",
      ph_status: "unknown",
      nutrient_status: {
        N: "unknown", P: "unknown", K: "unknown", S: "unknown", Ca: "unknown", Mg: "unknown",
      },
      organic_matter_status: "unknown",
      texture_class: "",
      compaction_status: "unknown",
    },
    soil_override: {
      clay_pct: "", sand_pct: "", silt_pct: "", organic_matter_pct: "",
      field_capacity_m3m3: "", wilting_point_m3m3: "", bulk_density_g_cm3: "",
      awc_mm_rootzone: "", root_depth_cm: "", drainage_class: "", hydrologic_group: "",
      ph_h2o: "", phosphorus_mg_dm3: "", potassium_mg_dm3: "", nitrogen_mg_dm3: "",
      electrical_conductivity_ds_m: "",
    },
    pests: [],
    crop_history: [],
  };
}

export function loadProducerSettings() {
  if (typeof window === "undefined") return { farmName: "", preferences: DEFAULT_PREFERENCES, profiles: {} };
  try {
    const saved = JSON.parse(window.localStorage.getItem(PRODUCER_SETTINGS_KEY) || "{}");
    return {
      farmName: typeof saved.farmName === "string" ? saved.farmName : "",
      preferences: { ...DEFAULT_PREFERENCES, ...(saved.preferences || {}) },
      profiles: saved.profiles && typeof saved.profiles === "object" ? saved.profiles : {},
    };
  } catch {
    return { farmName: "", preferences: DEFAULT_PREFERENCES, profiles: {} };
  }
}

export function saveProducerSettings(settings) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(PRODUCER_SETTINGS_KEY, JSON.stringify(settings));
  window.dispatchEvent(new CustomEvent("cerradoshift:settings-updated", { detail: settings }));
}

export function getFieldSettings(fieldId) {
  const settings = loadProducerSettings();
  const key = fieldId ? String(fieldId) : "__default__";
  const profile = settings.profiles[key] || createEmptyFieldProfile();
  return { ...profile, preferences: settings.preferences, farmName: settings.farmName };
}

export function loadSavedFields() {
  if (typeof window === "undefined") return [];
  try {
    const value = JSON.parse(window.localStorage.getItem(FIELDS_STORAGE_KEY) || "[]");
    return Array.isArray(value) ? value : [];
  } catch {
    return [];
  }
}

export function toNumberOrUndefined(value) {
  if (value === "" || value === null || value === undefined) return undefined;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

/** Constrói o pedido no formato exato aceito por RecommendationRequest. */
export function buildRecommendationPayload(profile, preferences, fieldRecord = null) {
  const rotation = profile?.rotation || {};
  const field = profile?.field || {};
  const soil = profile?.soil_test || {};
  const currentCrop = rotation.current_crop || profile?.current_commercial_crop || "";
  const nextCrop = rotation.next_crop || "";
  const hasRotationPair = Boolean(currentCrop && nextCrop);

  const pestStatus = rotation.pratylenchus_brachyurus_status || "unknown";
  const pests = [...(profile?.pests || [])]
    .filter((item) => item.pest_id && String(item.pest_id).trim().length >= 2)
    .map((item) => ({
      pest_id: String(item.pest_id).trim(),
      status: item.status || "unknown",
      severity: item.severity || "unknown",
      observed_date: item.observed_date || null,
      notes: item.notes || null,
    }));

  if (pestStatus !== "unknown" && !pests.some((item) => item.pest_id === "pratylenchus_brachyurus")) {
    pests.push({
      pest_id: "pratylenchus_brachyurus",
      status: pestStatus === "present" ? "confirmed" : "not_detected",
      severity: "unknown",
      observed_date: null,
      notes: "Situação informada na configuração do talhão.",
    });
  }

  const hasSoilData = Boolean(
    soil.sample_date || soil.laboratory || soil.ph_value !== "" || soil.ph_method ||
    soil.ph_status !== "unknown" || soil.organic_matter_status !== "unknown" ||
    soil.texture_class || soil.compaction_status !== "unknown" ||
    Object.values(soil.nutrient_status || {}).some((value) => value !== "unknown")
  );

  const recommendationField = {
    area_ha: toNumberOrUndefined(field.area_ha) ?? toNumberOrUndefined(fieldRecord?.area),
    slope_percent: toNumberOrUndefined(field.slope_percent),
    irrigation_system: field.irrigation_system || "unknown",
    irrigation_efficiency: toNumberOrUndefined(field.irrigation_efficiency_pct) === undefined
      ? undefined : toNumberOrUndefined(field.irrigation_efficiency_pct) / 100,
    water_limited: Boolean(field.water_limited),
    available_machinery: Array.isArray(field.available_machinery) ? field.available_machinery : [],
    budget_level: field.budget_level || "unknown",
    cotton_years_since_last: toNumberOrUndefined(field.cotton_years_since_last),
  };

  // Remove undefined para manter o JSON limpo; a API aplica seus próprios padrões.
  Object.keys(recommendationField).forEach((key) => {
    if (recommendationField[key] === undefined) delete recommendationField[key];
  });

  return {
    current_commercial_crop: currentCrop || null,
    crop_stage: profile?.crop_stage || null,
    field: recommendationField,
    soil_test: hasSoilData ? {
      sample_date: soil.sample_date || null,
      laboratory: soil.laboratory || null,
      ph_value: toNumberOrUndefined(soil.ph_value) ?? null,
      ph_method: soil.ph_method || null,
      ph_status: soil.ph_status || "unknown",
      nutrient_status: soil.nutrient_status || {},
      organic_matter_status: soil.organic_matter_status || "unknown",
      texture_class: soil.texture_class || null,
      compaction_status: soil.compaction_status || "unknown",
    } : null,
    pests,
    crop_history: (profile?.crop_history || [])
      .filter((entry) => entry.crop_id)
      .map((entry) => ({
        crop_id: entry.crop_id,
        season_label: entry.season_label || null,
        planting_date: entry.planting_date || null,
        harvest_date: entry.harvest_date || null,
        notes: entry.notes || null,
      })),
    preferences: {
      priorities: preferences?.priorities || DEFAULT_PREFERENCES.priorities,
      objective: preferences?.objective || "balanced",
      avoided_transition_crops: preferences?.avoided_transition_crops || [],
      risk_tolerance: preferences?.risk_tolerance || "medium",
      notes: preferences?.notes || null,
    },
    rotation: {
      current_crop: hasRotationPair ? currentCrop : null,
      next_crop: hasRotationPair ? nextCrop : null,
      days_available: hasRotationPair ? toNumberOrUndefined(rotation.days_available) ?? null : null,
      pratylenchus_brachyurus_status: pestStatus,
    },
    model_results: {},
    evaluation_date: new Date().toISOString().slice(0, 10),
  };
}

/** Converte a configuração local em parâmetros para o contexto ambiental /v1/field-context. */
export function buildFieldContextExtras(profile = {}) {
  const field = profile.field || {};
  const rotation = profile.rotation || {};
  const irrigationSystem = field.irrigation_system || "unknown";
  const irrigation = irrigationSystem === "rainfed" ? "rainfed"
    : irrigationSystem === "unknown" ? undefined : "irrigated";

  const result = {
    irrigation,
    current_crop: rotation.current_crop || profile.current_commercial_crop || undefined,
    target_crop: rotation.next_crop || rotation.current_crop || profile.current_commercial_crop || undefined,
  };

  const soil = profile.soil_override || {};
  const soilOverride = {};
  const mapping = {
    clay_pct: "clay_pct", sand_pct: "sand_pct", silt_pct: "silt_pct",
    organic_matter_pct: "organic_matter_pct", field_capacity_m3m3: "field_capacity_m3m3",
    wilting_point_m3m3: "wilting_point_m3m3", bulk_density_g_cm3: "bulk_density_g_cm3",
    awc_mm_rootzone: "awc_mm_rootzone", root_depth_cm: "root_depth_cm",
    ph_h2o: "ph_h2o", phosphorus_mg_dm3: "phosphorus_mg_dm3",
    potassium_mg_dm3: "potassium_mg_dm3", nitrogen_mg_dm3: "nitrogen_mg_dm3",
    electrical_conductivity_ds_m: "electrical_conductivity_ds_m",
  };
  Object.entries(mapping).forEach(([source, target]) => {
    const value = toNumberOrUndefined(soil[source]);
    if (value !== undefined) soilOverride[target] = value;
  });
  ["drainage_class", "hydrologic_group"].forEach((key) => {
    if (soil[key]) soilOverride[key] = soil[key];
  });
  if (soil.ph_h2o === "" && profile.soil_test?.ph_value !== "" && profile.soil_test?.ph_value != null) {
    const ph = toNumberOrUndefined(profile.soil_test.ph_value);
    if (ph !== undefined) soilOverride.ph_h2o = ph;
  }
  if (Object.keys(soilOverride).length) result.soil_override = soilOverride;
  return result;
}
