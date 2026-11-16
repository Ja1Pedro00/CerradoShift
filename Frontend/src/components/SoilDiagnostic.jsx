import { useI18n } from "../i18n";

import { useState } from "react";
import { diagnoseSoil } from "../services/soilApi";
import "./SoilDiagnostic.css";

const initialSoil = {
  clay_pct: "40",
  sand_pct: "45",
  silt_pct: "15",
  ph_h2o: "5.2",
  organic_matter_pct: "2.8",
  field_capacity_m3m3: "0.32",
  wilting_point_m3m3: "0.17",
  phosphorus_mg_dm3: "8",
  potassium_mg_dm3: "75",
};

const fields = [
  ["clay_pct", "Argila (%)"],
  ["sand_pct", "Areia (%)"],
  ["silt_pct", "Silte (%)"],
  ["ph_h2o", "pH em água"],
  ["organic_matter_pct", "Matéria orgânica (%)"],
  ["field_capacity_m3m3", "Capacidade de campo (m³/m³)"],
  ["wilting_point_m3m3", "Ponto de murcha (m³/m³)"],
  ["phosphorus_mg_dm3", "Fósforo (mg/dm³)"],
  ["potassium_mg_dm3", "Potássio (mg/dm³)"],
];

function show(value, unit = "", na = "Indisponível") {
  if (value === null || value === undefined) return na;
  return `${value}${unit}`;
}

export default function SoilDiagnostic({
  lat,
  lon,
}) {
  const { t } = useI18n();
  const na = t("Indisponível");
  const [mode, setMode] = useState("automatic");
  const [soil, setSoil] = useState(initialSoil);
  const [depth, setDepth] = useState(30);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [debugOpen, setDebugOpen] = useState(false);

  async function analyze() {
    const latitude = Number(lat);
    const longitude = Number(lon);
    const rootDepth = Number(depth);
    if (!Number.isFinite(latitude) || !Number.isFinite(longitude) ||
        latitude < -90 || latitude > 90 || longitude < -180 || longitude > 180) {
      setError(t("Selecione um talhão com coordenadas válidas antes de consultar o solo."));
      return;
    }
    if (!Number.isFinite(rootDepth) || rootDepth < 10 || rootDepth > 300) {
      setError(t("A profundidade deve estar entre 10 e 300 cm."));
      return;
    }

    setLoading(true);
    setError("");
    setResult(null);

    const payload = {
      lat: latitude,
      lon: longitude,
      root_depth_cm: rootDepth,
    };

    if (mode === "manual") {
      const override = {};

      for (const [key, value] of Object.entries(soil)) {
        if (String(value).trim() !== "") {
          const number = Number(String(value).replace(",", "."));
          if (!Number.isFinite(number)) {
            setError(t("Valor inválido: {campo}", { campo: key }));
            setLoading(false);
            return;
          }
          override[key] = number;
        }
      }

      override.root_depth_cm = Number(depth);
      payload.soil_override = override;
    }

    try {
      const data = await diagnoseSoil(payload);
      console.info("[CerradoShift] Diagnóstico regional:", data);
      setResult(data);
    } catch (err) {
      setError(
        err.name === "AbortError"
          ? t("A consulta excedeu o limite de tempo.")
          : err.message
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="soil-diagnostic">
      <h2>{t("Diagnóstico do Solo")}</h2>

      <p>
        {t("Localização:")} {Number.isFinite(Number(lat)) && lat != null && Number.isFinite(Number(lon)) && lon != null
          ? `${Number(lat).toFixed(4)}, ${Number(lon).toFixed(4)}`
          : t("Nenhum talhão selecionado")}
      </p>

      <div className="soil-controls">
        <label>
          {t("Origem dos dados")}
          <select
            value={mode}
            onChange={(e) => {
              setMode(e.target.value);
              setResult(null);
            }}
          >
            <option value="automatic">{t("Consulta automática")}</option>
            <option value="manual">{t("Análise de laboratório")}</option>
          </select>
        </label>

        <label>
          {t("Profundidade analisada (cm)")}
          <input
            type="number"
            min="10"
            max="300"
            value={depth}
            onChange={(e) => setDepth(e.target.value)}
          />
        </label>
      </div>

      {mode === "manual" && (
        <div className="soil-form">
          {fields.map(([key, label]) => (
            <label key={key}>
              {t(label)}
              <input
                type="text"
                inputMode="decimal"
                value={soil[key]}
                onChange={(e) =>
                  setSoil((prev) => ({
                    ...prev,
                    [key]: e.target.value,
                  }))
                }
              />
            </label>
          ))}
        </div>
      )}

      <button onClick={analyze} disabled={loading}>
        {loading ? t("Analisando solo...") : t("Gerar diagnóstico")}
      </button>

      {error && <p role="alert" className="soil-error">{error}</p>}

      {result && (
        <div className="soil-results">
          <h3>{t("Resultados")}</h3>
          <p>{t("Fonte:")} {t(result.soil?.provider) || t("Nenhuma fonte forneceu atributos quantitativos válidos")}</p>
          <p>{t("Confiança:")} {result.confidence || t("não informada")}</p>
          <p>{t("Modo de aquisição:")} {result.soil_data_mode || t("não informado")}</p>
          {result.soil_data_mode === "regional_br" && (
            <p>{t("Os provedores brasileiros foram consultados, mas ainda não forneceram atributos quantitativos válidos para o talhão.")}</p>
          )}
          {result.regional_sources && Object.keys(result.regional_sources).length > 0 && (
            <section className="soil-sources" aria-label={t("Estado dos provedores")}>
              <h3>{t("Estado das fontes de solo")}</h3>
              {Object.entries(result.regional_sources).map(([name, source]) => (
                <p key={name}>
                  <strong>{name}:</strong> {t(source?.status || "sem estado")}
                  {source?.detail ? ` — ${t(source.detail)}` : ""}
                </p>
              ))}
            </section>
          )}

          <div className="soil-grid">
            <article>
              <h4>{t("Textura")}</h4>
              <strong>{show(result.soil?.texture_class && t(result.soil.texture_class), "", na)}</strong>
            </article>
            <article>
              <h4>pH</h4>
              <strong>{show(result.soil?.ph_h2o, "", na)}</strong>
            </article>
            <article>
              <h4>{t("Matéria orgânica")}</h4>
              <strong>
                {show(result.soil?.organic_matter_pct, "%", na)}
              </strong>
            </article>
            <article>
              <h4>{t("Água disponível")}</h4>
              <strong>
                {show(result.soil?.awc_mm_rootzone, " mm", na)}
              </strong>
            </article>
          </div>

          <h3>{t("Interpretação científica")}</h3>
          <div className="soil-findings">
            {(result.findings || []).map((finding) => (
              <article key={finding.code} className={finding.level}>
                <h4>{t(finding.title)}</h4>
                <p>{t(finding.detail)}</p>
                <p>
                  <strong>{t("Próxima ação:")} </strong>
                  {t(finding.suggested_action)}
                </p>
              </article>
            ))}
          </div>

          {(result.warnings || []).length > 0 && (
            <section role="status">
              <h3>{t("Avisos sobre os dados")}</h3>
              {result.warnings.map((warning, index) => (
                <p key={index}>{t(warning)}</p>
              ))}
            </section>
          )}

          <details open={debugOpen} onToggle={(event) => setDebugOpen(event.currentTarget.open)}>
            <summary>{t("Resposta técnica da API")}</summary>
            <pre style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>
              {JSON.stringify(result, null, 2)}
            </pre>
          </details>
          <small>{t(result.disclaimer)}</small>
        </div>
      )}
    </section>
  );
}
