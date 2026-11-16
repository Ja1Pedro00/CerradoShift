import { getFieldSettings, buildFieldContextExtras } from "./settingsStorage";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers: {
        ...(options.body ? { "Content-Type": "application/json" } : {}),
        ...options.headers,
      },
    });
  } catch {
    throw new Error(`Não foi possível conectar à API em ${API_BASE_URL}. Confira se o backend está ativo e se VITE_API_BASE_URL está correto.`);
  }
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json")
    ? await response.json().catch(() => null)
    : await response.text().catch(() => "");
  if (!response.ok) {
    const detail = typeof payload?.detail === "string" ? payload.detail
      : payload?.detail?.error || payload?.detail?.how_to_fix || payload?.detail?.hint
        ? [payload.detail.error, payload.detail.how_to_fix, payload.detail.hint].filter(Boolean).join(" — ")
        : typeof payload === "string" ? payload : `HTTP ${response.status}`;
    const error = new Error(detail || `HTTP ${response.status}`);
    error.status = response.status;
    error.payload = payload;
    throw error;
  }
  return payload;
}

export const api = {
  baseUrl: API_BASE_URL,
  health: () => request("/health"),
  sources: () => request("/v1/sources"),
  fieldContext: (body) => request("/v1/field-context", { method: "POST", body: JSON.stringify(body) }),
  vegetationSeries: (body) => request("/v1/vegetation-series", { method: "POST", body: JSON.stringify(body) }),
  plan: (body) => request("/v1/plan", { method: "POST", body: JSON.stringify(body) }),
  rotationOptions: (body) => request("/v1/rotation-options", { method: "POST", body: JSON.stringify(body) }),
  cropCatalog: () => request("/api/v1/crop-catalog"),
  cerradoCatalog: () => request("/api/v1/cerrado-mvp/catalog"),
  assessRotation: (body) => request("/api/v1/assessments/rotation", { method: "POST", body: JSON.stringify(body) }),
  assessTransitionOptions: (body) => request("/api/v1/assessments/cerrado-transition-options", { method: "POST", body: JSON.stringify(body) }),
  assessRecommendations: (body) => request("/api/v1/assessments/recommendations", { method: "POST", body: JSON.stringify(body) }),
  assessVegetationIndices: (body) => request("/api/v1/assessments/vegetation-indices", { method: "POST", body: JSON.stringify(body) }),
  assessVegetationAnomaly: (body) => request("/api/v1/assessments/vegetation-anomaly", { method: "POST", body: JSON.stringify(body) }),
  assessErosion: (body) => request("/api/v1/assessments/erosion", { method: "POST", body: JSON.stringify(body) }),
  assessPhenology: (body) => request("/api/v1/assessments/phenology-thermal", { method: "POST", body: JSON.stringify(body) }),
  assessDualKc: (body) => request("/api/v1/assessments/dual-kc", { method: "POST", body: JSON.stringify(body) }),
  assessYieldWaterResponse: (body) => request("/api/v1/assessments/yield-water-response", { method: "POST", body: JSON.stringify(body) }),
  assessField: (body) => request("/api/v1/assessments/field", { method: "POST", body: JSON.stringify(body) }),
};

export function fieldRequest(talhao, extra = {}) {
  const geometry = talhao?.geojson?.geometry || talhao?.geometry;
  if (!geometry || !["Polygon", "MultiPolygon"].includes(geometry.type)) {
    throw new Error("Este talhão não possui um polígono GeoJSON válido. Redesenhe ou edite o talhão no mapa.");
  }
  const producerSettings = getFieldSettings(talhao.id);
  const configuredArea = Number(producerSettings.field?.area_ha);
  const settingsExtras = buildFieldContextExtras(producerSettings);
  return {
    geometry,
    field_id: talhao.id,
    area_ha: Number.isFinite(configuredArea) && configuredArea > 0
      ? configuredArea
      : Number(talhao.area) > 0 ? Number(talhao.area) : undefined,
    window_days: 365,
    forecast_days: 14,
    ...settingsExtras,
    ...extra,
  };
}

export function vegetationRequest(talhao) {
  const geometry = talhao?.geojson?.geometry || talhao?.geometry;
  if (!geometry || !["Polygon", "MultiPolygon"].includes(geometry.type)) {
    throw new Error("Este talhão não possui um polígono GeoJSON válido.");
  }
  return { geometry, max_scenes: 8, include_evi: true };
}
