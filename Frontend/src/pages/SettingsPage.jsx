import { useEffect, useMemo, useState } from "react";
import {
  Save, RotateCcw, Download, Upload, RefreshCw, CheckCircle2,
  AlertTriangle, Wifi, Database, Sprout, Droplets, FlaskConical, Bug,
  SlidersHorizontal, ChevronDown, Info,
} from "lucide-react";
import { api } from "../services/api";
import { useI18n } from "../i18n";
import {
  DEFAULT_PREFERENCES,
  buildRecommendationPayload,
  createEmptyFieldProfile,
  loadProducerSettings,
  loadSavedFields,
  saveProducerSettings,
} from "../services/settingsStorage";
import "./SettingsPage.css";

const CROPS = [
  { id: "soybean", label: "Soja" },
  { id: "maize", label: "Milho" },
  { id: "cotton", label: "Algodão" },
];

const TRANSITION_CROPS = [
  { id: "millet", label: "Milheto" },
  { id: "urochloa_ruziziensis", label: "Urochloa ruziziensis (braquiária-ruziziensis)" },
  { id: "crotalaria_spectabilis", label: "Crotalária-espectábilis" },
  { id: "crotalaria_ochroleuca", label: "Crotalária-ochroleuca" },
];
const HISTORY_CROPS = [...CROPS, ...TRANSITION_CROPS];

const PRIORITIES = [
  { id: "water_saving", label: "Economizar água", hint: "Eficiência hídrica e redução de perdas." },
  { id: "soil_cover", label: "Cobrir e proteger o solo", hint: "Palhada, biomassa e cobertura entre safras." },
  { id: "nutrient_cycling", label: "Ciclagem de nutrientes", hint: "Aproveitamento e retorno de nutrientes." },
  { id: "pest_break", label: "Quebra de ciclos de pragas", hint: "Evitar continuidade de culturas hospedeiras." },
  { id: "profitability", label: "Rentabilidade", hint: "Comparar custos, preços e receitas quando disponíveis." },
  { id: "soil_recovery", label: "Recuperação do solo", hint: "Matéria orgânica, erosão e estrutura do solo." },
];

const MACHINERY = [
  "Semeadora/plantadeira", "Semeadora de cobertura", "Distribuidor de fertilizantes",
  "Pulverizador", "Roçadeira", "Rolo-faca", "Triturador de palhada", "Subsolador",
];

const PEST_STATUS = [
  { value: "confirmed", label: "Confirmado em análise/diagnóstico" },
  { value: "suspected", label: "Suspeito, ainda sem confirmação" },
  { value: "not_detected", label: "Não detectado na análise" },
  { value: "unknown", label: "Não sei / não avaliado" },
];

const SOIL_STATUS = [
  { value: "unknown", label: "Não sei / não informado" },
  { value: "low", label: "Baixo" },
  { value: "adequate", label: "Adequado" },
  { value: "high", label: "Alto" },
];

function readFieldsSafely() {
  return loadSavedFields();
}

function createInitialSettings() {
  const stored = loadProducerSettings();
  return {
    farmName: stored.farmName || "",
    preferences: { ...DEFAULT_PREFERENCES, ...(stored.preferences || {}) },
    profiles: stored.profiles || {},
  };
}

function updateNested(current, section, key, value) {
  return {
    ...current,
    [section]: { ...(current[section] || {}), [key]: value },
  };
}

function Field({ label, hint, children, className = "" }) {
  const { t } = useI18n();
  return (
    <label className={`settings-field ${className}`}>
      <span className="settings-field-label">{t(label)}</span>
      {children}
      {hint && <small className="settings-field-hint">{t(hint)}</small>}
    </label>
  );
}

function Section({ icon: Icon, title, description, children, id }) {
  const { t } = useI18n();
  return (
    <section className="settings-section" id={id}>
      <div className="settings-section-heading">
        <span className="settings-section-icon"><Icon size={19} /></span>
        <div><h2>{t(title)}</h2><p>{t(description)}</p></div>
      </div>
      <div className="settings-section-body">{children}</div>
    </section>
  );
}

function SelectOptions({ options }) {
  const { t } = useI18n();
  return options.map((option) => (
    <option key={option.value} value={option.value}>{t(option.label)}</option>
  ));
}

function sourcePresentation(source) {
  if (source.in_api) return { label: "Integrada no backend", ready: true };
  if (source.access === "key") {
    return { label: `Integração pendente — requer ${source.credential || "credencial"}`, ready: false };
  }
  if (source.access === "open") return { label: "Integração pendente — acesso aberto", ready: false };
  return { label: "Estado não informado", ready: false };
}

export default function SettingsPage() {
  const { t } = useI18n();
  const [talhoes, setTalhoes] = useState(readFieldsSafely);
  const [settings, setSettings] = useState(createInitialSettings);
  const [selectedFieldId, setSelectedFieldId] = useState(() => readFieldsSafely()[0]?.id || "");
  const [savedMessage, setSavedMessage] = useState("");
  const [formError, setFormError] = useState("");
  const [apiStatus, setApiStatus] = useState({ loading: true, online: null, sources: [], error: "" });
  const [testState, setTestState] = useState({ loading: false, error: "", result: null });
  const [importMessage, setImportMessage] = useState("");

  const profileKey = selectedFieldId ? String(selectedFieldId) : "__default__";
  const profile = settings.profiles[profileKey] || createEmptyFieldProfile();
  const selectedField = talhoes.find((item) => String(item.id) === String(selectedFieldId)) || null;

  useEffect(() => {
    const refreshFields = () => setTalhoes(readFieldsSafely());
    window.addEventListener("storage", refreshFields);
    window.addEventListener("cerradoshift:fields-updated", refreshFields);
    return () => {
      window.removeEventListener("storage", refreshFields);
      window.removeEventListener("cerradoshift:fields-updated", refreshFields);
    };
  }, []);

  useEffect(() => {
    let active = true;
    async function checkApi() {
      setApiStatus({ loading: true, online: null, sources: [], error: "" });
      try {
        const [health, sources] = await Promise.all([api.health(), api.sources()]);
        if (!active) return;
        setApiStatus({
          loading: false,
          online: true,
          health,
          sources: Array.isArray(sources?.sources) ? sources.sources : [],
          error: "",
        });
      } catch (error) {
        if (!active) return;
        setApiStatus({ loading: false, online: false, sources: [], error: error.message });
      }
    }
    checkApi();
    return () => { active = false; };
  }, []);

  const profileCompleteness = useMemo(() => {
    const checks = [
      Boolean(profile.rotation?.current_crop),
      Boolean(profile.field?.irrigation_system && profile.field.irrigation_system !== "unknown"),
      Boolean(profile.soil_test?.sample_date || profile.soil_test?.ph_status !== "unknown"),
      Boolean(profile.rotation?.pratylenchus_brachyurus_status !== "unknown"),
      Boolean(settings.preferences?.priorities?.length),
    ];
    return Math.round((checks.filter(Boolean).length / checks.length) * 100);
  }, [profile, settings.preferences]);

  function updateProfile(section, key, value) {
    setSavedMessage("");
    setSettings((current) => {
      const oldProfile = current.profiles[profileKey] || createEmptyFieldProfile();
      return {
        ...current,
        profiles: {
          ...current.profiles,
          [profileKey]: updateNested(oldProfile, section, key, value),
        },
      };
    });
  }

  function updateRotation(key, value) { updateProfile("rotation", key, value); }
  function updateField(key, value) { updateProfile("field", key, value); }
  function updateSoil(key, value) { updateProfile("soil_test", key, value); }
  function updateSoilOverride(key, value) { updateProfile("soil_override", key, value); }

  function updateNutrient(key, value) {
    setSavedMessage("");
    setSettings((current) => {
      const oldProfile = current.profiles[profileKey] || createEmptyFieldProfile();
      const soil = oldProfile.soil_test || createEmptyFieldProfile().soil_test;
      return {
        ...current,
        profiles: {
          ...current.profiles,
          [profileKey]: {
            ...oldProfile,
            soil_test: { ...soil, nutrient_status: { ...soil.nutrient_status, [key]: value } },
          },
        },
      };
    });
  }

  function updatePreferences(key, value) {
    setSavedMessage("");
    setSettings((current) => ({
      ...current,
      preferences: { ...current.preferences, [key]: value },
    }));
  }

  function toggleArrayValue(section, key, value) {
    const currentValues = profile[section]?.[key] || [];
    const next = currentValues.includes(value)
      ? currentValues.filter((item) => item !== value)
      : [...currentValues, value];
    updateProfile(section, key, next);
  }

  function togglePreference(value) {
    const current = settings.preferences.priorities || [];
    updatePreferences("priorities", current.includes(value)
      ? current.filter((item) => item !== value)
      : [...current, value]);
  }

  function toggleAvoidCrop(value) {
    const current = settings.preferences.avoided_transition_crops || [];
    updatePreferences("avoided_transition_crops", current.includes(value)
      ? current.filter((item) => item !== value)
      : [...current, value]);
  }

  function addPest() {
    setSavedMessage("");
    setSettings((current) => {
      const old = current.profiles[profileKey] || createEmptyFieldProfile();
      return {
        ...current,
        profiles: {
          ...current.profiles,
          [profileKey]: {
            ...old,
            pests: [...(old.pests || []), {
              local_id: crypto.randomUUID(), pest_id: "", status: "suspected",
              severity: "unknown", observed_date: "", notes: "",
            }],
          },
        },
      };
    });
  }

  function updatePest(localId, key, value) {
    setSavedMessage("");
    setSettings((current) => {
      const old = current.profiles[profileKey] || createEmptyFieldProfile();
      return {
        ...current,
        profiles: {
          ...current.profiles,
          [profileKey]: {
            ...old,
            pests: (old.pests || []).map((pest) => pest.local_id === localId ? { ...pest, [key]: value } : pest),
          },
        },
      };
    });
  }

  function removePest(localId) {
    setSavedMessage("");
    setSettings((current) => {
      const old = current.profiles[profileKey] || createEmptyFieldProfile();
      return {
        ...current,
        profiles: {
          ...current.profiles,
          [profileKey]: {
            ...old,
            pests: (old.pests || []).filter((pest) => pest.local_id !== localId),
          },
        },
      };
    });
  }

  function addHistoryEntry() {
    setSavedMessage("");
    setSettings((current) => {
      const old = current.profiles[profileKey] || createEmptyFieldProfile();
      if ((old.crop_history || []).length >= 3) return current;
      return {
        ...current,
        profiles: {
          ...current.profiles,
          [profileKey]: {
            ...old,
            crop_history: [...(old.crop_history || []), {
              local_id: crypto.randomUUID(), crop_id: "", season_label: "",
              planting_date: "", harvest_date: "", notes: "",
            }],
          },
        },
      };
    });
  }

  function updateHistoryEntry(localId, key, value) {
    setSavedMessage("");
    setSettings((current) => {
      const old = current.profiles[profileKey] || createEmptyFieldProfile();
      return {
        ...current,
        profiles: {
          ...current.profiles,
          [profileKey]: {
            ...old,
            crop_history: (old.crop_history || []).map((entry) =>
              entry.local_id === localId ? { ...entry, [key]: value } : entry
            ),
          },
        },
      };
    });
  }

  function removeHistoryEntry(localId) {
    setSavedMessage("");
    setSettings((current) => {
      const old = current.profiles[profileKey] || createEmptyFieldProfile();
      return {
        ...current,
        profiles: {
          ...current.profiles,
          [profileKey]: {
            ...old,
            crop_history: (old.crop_history || []).filter((entry) => entry.local_id !== localId),
          },
        },
      };
    });
  }

  function setCurrentCrop(value) {
    setSavedMessage("");
    setSettings((current) => {
      const old = current.profiles[profileKey] || createEmptyFieldProfile();
      return {
        ...current,
        profiles: {
          ...current.profiles,
          [profileKey]: {
            ...old,
            current_commercial_crop: value,
            rotation: { ...(old.rotation || {}), current_crop: value },
          },
        },
      };
    });
  }

  function validateProfileForSave() {
    const field = profile.field || {};
    const rotation = profile.rotation || {};
    const currentCrop = rotation.current_crop || profile.current_commercial_crop;
    const nextCrop = rotation.next_crop;
    const days = rotation.days_available === "" || rotation.days_available == null
      ? null : Number(rotation.days_available);
    const efficiency = field.irrigation_efficiency_pct === "" || field.irrigation_efficiency_pct == null
      ? null : Number(field.irrigation_efficiency_pct);
    const ph = profile.soil_test?.ph_value === "" || profile.soil_test?.ph_value == null
      ? null : Number(profile.soil_test.ph_value);

    if (currentCrop && nextCrop && (days === null || !Number.isInteger(days) || days < 0 || days > 365)) {
      return "Informe de 0 a 365 dias entre as culturas para avaliar a rotação.";
    }
    if (efficiency !== null && (!Number.isFinite(efficiency) || efficiency <= 0 || efficiency > 100)) {
      return "A eficiência de irrigação deve ser maior que 0 e no máximo 100%.";
    }
    if (ph !== null && (!Number.isFinite(ph) || ph < 0 || ph > 14)) {
      return "O pH deve estar entre 0 e 14, conforme o laudo.";
    }
    for (const entry of profile.crop_history || []) {
      if (entry.planting_date && entry.harvest_date && entry.harvest_date < entry.planting_date) {
        return "Em uma safra do histórico, a colheita está antes da data de plantio.";
      }
    }
    return "";
  }

  function save() {
    setFormError("");
    const validationError = validateProfileForSave();
    if (validationError) {
      setFormError(validationError);
      return;
    }
    const next = {
      ...settings,
      profiles: {
        ...settings.profiles,
        [profileKey]: profile,
      },
    };
    try {
      saveProducerSettings(next);
      setSettings(next);
      setSavedMessage("Configurações salvas neste navegador.");
    } catch (error) {
      setFormError(`Não foi possível salvar: ${error.message}`);
    }
  }

  function resetProfile() {
    const next = { ...settings, profiles: { ...settings.profiles, [profileKey]: createEmptyFieldProfile() } };
    setSettings(next);
    saveProducerSettings(next);
    setSavedMessage("Dados deste talhão foram restaurados para os valores iniciais.");
  }

  function exportSettings() {
    // Exporta o perfil selecionado de forma explícita para permitir importação
    // em outro navegador, mesmo quando o ID local do talhão for diferente.
    const payload = {
      farmName: settings.farmName,
      preferences: settings.preferences,
      profiles: { [profileKey]: profile },
      exported_profile: profile,
      exported_field_name: selectedField?.nome || null,
      exported_at: new Date().toISOString(),
      format: "cerradoshift-producer-settings-v1",
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `cerradoshift-configuracoes-${selectedField?.nome || "padrao"}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  async function importSettings(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    setImportMessage("");
    try {
      const parsed = JSON.parse(await file.text());
      if (!parsed || typeof parsed !== "object" || !parsed.profiles || !parsed.preferences) {
        throw new Error("O arquivo não parece ser uma configuração CerradoShift válida.");
      }
      const importedProfile = parsed.exported_profile
        || parsed.profiles[String(selectedFieldId)]
        || parsed.profiles.__default__
        || (Object.keys(parsed.profiles).length === 1 ? Object.values(parsed.profiles)[0] : null);
      if (!importedProfile) {
        throw new Error("O arquivo contém vários talhões. Exporte novamente somente o talhão desejado.");
      }
      const next = {
        farmName: typeof parsed.farmName === "string" ? parsed.farmName : "",
        preferences: { ...DEFAULT_PREFERENCES, ...parsed.preferences },
        // Associa o perfil importado ao talhão atualmente selecionado neste dispositivo.
        profiles: { [profileKey]: importedProfile },
      };
      saveProducerSettings(next);
      setSettings(next);
      setImportMessage("Configuração importada e salva neste navegador.");
    } catch (error) {
      setImportMessage(`Não foi possível importar o arquivo: ${error.message}`);
    } finally {
      event.target.value = "";
    }
  }

  async function testApi() {
    setTestState({ loading: true, error: "", result: null });
    try {
      const validationError = validateProfileForSave();
      if (validationError) throw new Error(validationError);
      const body = buildRecommendationPayload(profile, settings.preferences, selectedField);
      const result = await api.assessRecommendations(body);
      setTestState({ loading: false, error: "", result });
    } catch (error) {
      setTestState({ loading: false, error: error.message, result: null });
    }
  }

  const priorities = settings.preferences.priorities || [];
  const avoidedCrops = settings.preferences.avoided_transition_crops || [];

  return (
    <div className="settings-page">
      <div className="page-heading settings-page-heading">
        <div>
          <h1>{t("Configurações do produtor")}</h1>
          <p>{t("Informe as condições da propriedade e suas prioridades para personalizar as análises e recomendações do CerradoShift.")}</p>
        </div>
        <div className="settings-progress" aria-label={`Preenchimento aproximado ${profileCompleteness}%`}>
          <strong>{profileCompleteness}%</strong><span>{t("perfil preenchido")}</span>
        </div>
      </div>

      <div className="settings-info-banner">
        <Info size={18} />
        <div><strong>{t("Preencha apenas o que você sabe.")}</strong><span>{t("Campos desconhecidos podem ficar em branco. O CerradoShift não deve inventar valores de solo, pragas ou manejo.")}</span></div>
      </div>

      <Section icon={Sprout} title={t("Propriedade e talhão")} description="As configurações abaixo ficam associadas ao talhão selecionado.">
        <div className="settings-grid">
          <Field label={t("Nome da propriedade (opcional)")}>
            <input value={settings.farmName} onChange={(event) => { setSavedMessage(""); setSettings((current) => ({ ...current, farmName: event.target.value })); }} placeholder={t("Ex.: Fazenda Boa Vista")} maxLength={120}/>
          </Field>
          <Field label={t("Talhão que deseja configurar")} hint={t("Cadastre ou desenhe um talhão na página Mapa da Propriedade.")}>
            <select value={selectedFieldId} onChange={(event) => { setSelectedFieldId(event.target.value); setTestState({ loading: false, error: "", result: null }); }}>
              <option value="">{t("Configuração padrão (sem talhão selecionado)")}</option>
              {talhoes.map((field) => <option key={field.id} value={field.id}>{field.nome} {Number.isFinite(Number(field.area)) ? `— ${Number(field.area).toFixed(2)} ha` : ""}</option>)}
            </select>
          </Field>
        </div>
        {selectedField ? (
          <div className="settings-field-summary"><CheckCircle2 size={17}/><span><strong>{selectedField.nome}</strong> — {Number(selectedField.area || 0).toLocaleString("pt-BR", { maximumFractionDigits: 2 })} ha cadastrado no mapa.</span></div>
        ) : (
          <div className="settings-muted-note">{t("Nenhum talhão selecionado. Você pode salvar preferências gerais agora e associar os dados de manejo depois.")}</div>
        )}
      </Section>

      <Section icon={Sprout} title={t("Cultivo e planejamento de rotação")} description="O CerradoShift começa com soja, milho e algodão, além de quatro culturas de transição.">
        <div className="settings-grid">
          <Field label={t("Cultura comercial atual")}>
            <select value={profile.rotation?.current_crop || profile.current_commercial_crop || ""} onChange={(event) => setCurrentCrop(event.target.value)}>
              <option value="">{t("Não informado")}</option>
              {CROPS.map((crop) => <option key={crop.id} value={crop.id}>{t(crop.label)}</option>)}
            </select>
          </Field>
          <Field label={t("Próxima cultura comercial que deseja avaliar")}>
            <select value={profile.rotation?.next_crop || ""} onChange={(event) => updateRotation("next_crop", event.target.value)}>
              <option value="">{t("Ainda não definida")}</option>
              {CROPS.map((crop) => <option key={crop.id} value={crop.id}>{t(crop.label)}</option>)}
            </select>
          </Field>
          <Field label={t("Estágio atual da cultura")} hint={t("Informe a fase observada; não precisa saber o código fenológico.")}>
            <select value={profile.crop_stage || ""} onChange={(event) => { setSavedMessage(""); setSettings((current) => ({ ...current, profiles: { ...current.profiles, [profileKey]: { ...profile, crop_stage: event.target.value } } })); }}>
              <option value="">{t("Não informado")}</option>
              <option value="emergence">{t("Emergência")}</option>
              <option value="vegetative">{t("Vegetativo")}</option>
              <option value="flowering">{t("Florescimento")}</option>
              <option value="grain_filling">{t("Formação / enchimento de grãos")}</option>
              <option value="maturation">{t("Maturação")}</option>
              <option value="harvest">{t("Próximo da colheita")}</option>
            </select>
          </Field>
          <Field label={t("Dias disponíveis entre as culturas")} hint={t("Necessário quando informar cultura atual e próxima cultura.")}>
            <input type="number" min="0" max="365" step="1" value={profile.rotation?.days_available ?? ""} onChange={(event) => updateRotation("days_available", event.target.value)} placeholder={t("Ex.: 70")}/>
          </Field>
          <Field label={t("Anos desde o último plantio de algodão na mesma gleba")} hint={t("Use quando a próxima cultura for algodão.")}>
            <input type="number" min="0" max="30" step="1" value={profile.field?.cotton_years_since_last ?? ""} onChange={(event) => updateField("cotton_years_since_last", event.target.value)} placeholder={t("Ex.: 3")}/>
          </Field>
          <Field label={t("Situação de Pratylenchus brachyurus")} hint={t("Use o resultado de análise nematológica, quando disponível.")}>
            <select value={profile.rotation?.pratylenchus_brachyurus_status || "unknown"} onChange={(event) => updateRotation("pratylenchus_brachyurus_status", event.target.value)}>
              <option value="unknown">{t("Desconhecida / não analisada")}</option>
              <option value="present">{t("Presente / confirmado")}</option>
              <option value="not_detected">{t("Não detectado na análise")}</option>
            </select>
          </Field>
        </div>
        <div className="settings-muted-note">{t("A janela em dias é apenas uma informação inicial. A viabilidade de cada cobertura também depende da época, chuva remanescente, cultivar, semeadora e manejo.")}</div>
        <div className="settings-history-heading">
          <div><strong>{t("Histórico das últimas 2–3 safras")}</strong><small>{t("Cadastre da safra mais antiga para a mais recente. Essas informações ajudam a avaliar a sequência de hospedeiros.")}</small></div>
          <button type="button" className="settings-secondary-button" onClick={addHistoryEntry} disabled={(profile.crop_history || []).length >= 3}>{t("+ Adicionar safra")}</button>
        </div>
        {(profile.crop_history || []).length > 0 ? (profile.crop_history || []).map((entry, index) => (
          <div className="settings-history-row" key={entry.local_id || `history-${index}`}>
            <div className="settings-history-order">{index + 1}</div>
            <Field label={t("Cultura da safra")}>
              <select value={entry.crop_id || ""} onChange={(event) => updateHistoryEntry(entry.local_id, "crop_id", event.target.value)}>
                <option value="">{t("Selecione")}</option>
                {HISTORY_CROPS.map((crop) => <option key={crop.id} value={crop.id}>{t(crop.label)}</option>)}
              </select>
            </Field>
            <Field label={t("Identificação da safra")}>
              <input value={entry.season_label || ""} onChange={(event) => updateHistoryEntry(entry.local_id, "season_label", event.target.value)} placeholder={t("Ex.: Safra 2024/25")} maxLength={80}/>
            </Field>
            <Field label={t("Data de plantio")}>
              <input type="date" value={entry.planting_date || ""} onChange={(event) => updateHistoryEntry(entry.local_id, "planting_date", event.target.value)}/>
            </Field>
            <Field label={t("Data de colheita")}>
              <input type="date" value={entry.harvest_date || ""} onChange={(event) => updateHistoryEntry(entry.local_id, "harvest_date", event.target.value)}/>
            </Field>
            <button className="settings-remove-button" type="button" onClick={() => removeHistoryEntry(entry.local_id)}>{t("Remover")}</button>
          </div>
        )) : <div className="settings-muted-note">{t("Nenhuma safra anterior cadastrada. Adicione até três safras concluídas, se souber as informações.")}</div>}
      </Section>

      <Section icon={Droplets} title={t("Água e estrutura da propriedade")} description="Essas informações ajudam a interpretar o balanço hídrico e avaliar alternativas de manejo.">
        <div className="settings-grid">
          <Field label={t("Área do talhão (hectares)")}>
            <input type="number" min="0.01" step="0.01" value={profile.field?.area_ha || (selectedField?.area ? String(Number(selectedField.area).toFixed(2)) : "")} onChange={(event) => updateField("area_ha", event.target.value)} placeholder={selectedField?.area ? String(Number(selectedField.area).toFixed(2)) : "Ex.: 50"}/>
          </Field>
          <Field label={t("Declividade média (%)")} hint={t("Se não souber, deixe em branco; o relevo pode ser obtido por modelo de elevação quando integrado.")}>
            <input type="number" min="0" max="300" step="0.1" value={profile.field?.slope_percent ?? ""} onChange={(event) => updateField("slope_percent", event.target.value)} placeholder={t("Ex.: 4,5")}/>
          </Field>
          <Field label={t("Sistema de irrigação")}>
            <select value={profile.field?.irrigation_system || "unknown"} onChange={(event) => updateField("irrigation_system", event.target.value)}>
              <option value="unknown">{t("Não sei / não informado")}</option>
              <option value="rainfed">{t("Sequeiro (sem irrigação)")}</option>
              <option value="center_pivot">{t("Pivô central")}</option>
              <option value="sprinkler">{t("Aspersão")}</option>
              <option value="drip">{t("Gotejamento")}</option>
              <option value="furrow">{t("Sulcos")}</option>
              <option value="other">{t("Outro sistema")}</option>
            </select>
          </Field>
          <Field label={t("Eficiência estimada ou medida (%)")} hint={t("Informe somente se tiver medição ou dado técnico confiável.")}>
            <input type="number" min="1" max="100" step="1" value={profile.field?.irrigation_efficiency_pct ?? ""} onChange={(event) => updateField("irrigation_efficiency_pct", event.target.value)} placeholder={t("Ex.: 80")}/>
          </Field>
          <Field label={t("Orçamento disponível para mudanças")}>
            <select value={profile.field?.budget_level || "unknown"} onChange={(event) => updateField("budget_level", event.target.value)}>
              <option value="unknown">{t("Não informado")}</option>
              <option value="low">{t("Limitado")}</option>
              <option value="medium">{t("Moderado")}</option>
              <option value="high">{t("Flexível")}</option>
            </select>
          </Field>
        </div>
        <label className="settings-check settings-check-highlight">
          <input type="checkbox" checked={Boolean(profile.field?.water_limited)} onChange={(event) => updateField("water_limited", event.target.checked)}/>
          <span><strong>{t("Tenho limitação de disponibilidade de água")}</strong><small>{t("Ex.: restrição de captação, baixa vazão, reservatório limitado ou períodos de escassez.")}</small></span>
        </label>
        <div className="settings-subtitle">{t("Maquinário disponível")}</div>
        <div className="settings-check-grid">
          {MACHINERY.map((item) => (
            <label className="settings-check" key={item}>
              <input type="checkbox" checked={(profile.field?.available_machinery || []).includes(item)} onChange={() => toggleArrayValue("field", "available_machinery", item)}/>
              <span>{t(item)}</span>
            </label>
          ))}
        </div>
      </Section>

      <Section icon={FlaskConical} title={t("Análise de solo e fertilidade")} description="Registre a interpretação do laboratório. Não estime o pH nem a necessidade de adubo pela cultura escolhida.">
        <div className="settings-grid">
          <Field label={t("Data da análise")}>
            <input type="date" value={profile.soil_test?.sample_date || ""} onChange={(event) => updateSoil("sample_date", event.target.value)}/>
          </Field>
          <Field label={t("Laboratório (opcional)")}>
            <input value={profile.soil_test?.laboratory || ""} onChange={(event) => updateSoil("laboratory", event.target.value)} placeholder={t("Nome do laboratório")} maxLength={200}/>
          </Field>
          <Field label={t("pH informado no laudo")}>
            <input type="number" min="0" max="14" step="0.1" value={profile.soil_test?.ph_value ?? ""} onChange={(event) => updateSoil("ph_value", event.target.value)} placeholder={t("Ex.: 5,6")}/>
          </Field>
          <Field label={t("Método de determinação do pH")}>
            <select value={profile.soil_test?.ph_method || ""} onChange={(event) => updateSoil("ph_method", event.target.value)}>
              <option value="">{t("Não informado")}</option>
              <option value="water">{t("Água")}</option>
              <option value="cacl2">{t("CaCl₂")}</option>
              <option value="other">{t("Outro / consultar laudo")}</option>
            </select>
          </Field>
          <Field label={t("Interpretação do pH pelo laboratório")}>
            <select value={profile.soil_test?.ph_status || "unknown"} onChange={(event) => updateSoil("ph_status", event.target.value)}><SelectOptions options={SOIL_STATUS}/></select>
          </Field>
          <Field label={t("Classe de textura do solo")}>
            <select value={profile.soil_test?.texture_class || ""} onChange={(event) => updateSoil("texture_class", event.target.value)}>
              <option value="">{t("Não informada")}</option>
              <option value="arenoso">{t("Arenoso")}</option>
              <option value="franco_arenoso">{t("Franco-arenoso")}</option>
              <option value="argilo_arenoso">{t("Argilo-arenoso")}</option>
              <option value="franco">{t("Franco")}</option>
              <option value="argiloso">{t("Argiloso")}</option>
              <option value="muito_argiloso">{t("Muito argiloso")}</option>
              <option value="other">{t("Outra / consultar laudo")}</option>
            </select>
          </Field>
          <Field label={t("Matéria orgânica — interpretação")}>
            <select value={profile.soil_test?.organic_matter_status || "unknown"} onChange={(event) => updateSoil("organic_matter_status", event.target.value)}><SelectOptions options={SOIL_STATUS}/></select>
          </Field>
          <Field label={t("Compactação do solo")}>
            <select value={profile.soil_test?.compaction_status || "unknown"} onChange={(event) => updateSoil("compaction_status", event.target.value)}>
              <option value="unknown">{t("Não avaliada")}</option>
              <option value="suspected">{t("Suspeita")}</option>
              <option value="confirmed">{t("Confirmada por avaliação")}</option>
              <option value="not_detected">{t("Não detectada")}</option>
            </select>
          </Field>
        </div>
        <div className="settings-subtitle">{t("Interpretação dos nutrientes pelo laboratório")}</div>
        <div className="settings-nutrient-grid">
          {Object.entries(profile.soil_test?.nutrient_status || {}).map(([nutrient, value]) => (
            <Field key={nutrient} label={nutrient}>
              <select value={value || "unknown"} onChange={(event) => updateNutrient(nutrient, event.target.value)}><SelectOptions options={SOIL_STATUS}/></select>
            </Field>
          ))}
        </div>
        <details className="settings-advanced">
          <summary><ChevronDown size={16}/> {t("Dados físicos e valores numéricos adicionais (opcional)")}</summary>
          <p>{t("Use somente os valores que aparecem no laudo ou em medição técnica. Esses campos podem alimentar a consulta ambiental do talhão.")}</p>
          <div className="settings-grid settings-grid-3">
            {[
              ["clay_pct", "Argila (%)", "Ex.: 45"], ["sand_pct", "Areia (%)", "Ex.: 40"], ["silt_pct", "Silte (%)", "Ex.: 15"],
              ["organic_matter_pct", "Matéria orgânica (%)", "Ex.: 2,8"], ["field_capacity_m3m3", "Capacidade de campo (m³/m³)", "Ex.: 0,32"], ["wilting_point_m3m3", "Ponto de murcha (m³/m³)", "Ex.: 0,18"],
              ["bulk_density_g_cm3", "Densidade (g/cm³)", "Ex.: 1,3"], ["awc_mm_rootzone", "Água disponível (mm)", "Valor do laudo/modelo"], ["root_depth_cm", "Profundidade efetiva (cm)", "Ex.: 100"],
              ["ph_h2o", "pH em água", "Ex.: 5,6"], ["phosphorus_mg_dm3", "Fósforo (mg/dm³)", "Valor do laudo"], ["potassium_mg_dm3", "Potássio (mg/dm³)", "Valor do laudo"],
              ["nitrogen_mg_dm3", "Nitrogênio (mg/dm³)", "Valor do laudo"], ["electrical_conductivity_ds_m", "Condutividade elétrica (dS/m)", "Valor do laudo"],
            ].map(([key, label, placeholder]) => (
              <Field key={key} label={label}>
                <input type="number" step="any" value={profile.soil_override?.[key] ?? ""} onChange={(event) => updateSoilOverride(key, event.target.value)} placeholder={placeholder}/>
              </Field>
            ))}
            <Field label={t("Classe de drenagem")}>
              <input value={profile.soil_override?.drainage_class || ""} onChange={(event) => updateSoilOverride("drainage_class", event.target.value)} placeholder={t("Ex.: bem drenado")}/>
            </Field>
            <Field label={t("Grupo hidrológico")}>
              <select value={profile.soil_override?.hydrologic_group || ""} onChange={(event) => updateSoilOverride("hydrologic_group", event.target.value)}>
                <option value="">{t("Não informado")}</option><option value="A">{t("A")}</option><option value="B">{t("B")}</option><option value="C">{t("C")}</option><option value="D">{t("D")}</option>
              </select>
            </Field>
          </div>
        </details>
      </Section>

      <Section icon={Bug} title={t("Pragas e problemas fitossanitários")} description="Registre apenas organismos identificados ou suspeitos. A ausência de registro não significa ausência da praga.">
        <Field label={t("Situação de Pratylenchus brachyurus")} hint={t("Este campo também aparece na seção de rotação; os dois ficam sincronizados.")}>
          <select value={profile.rotation?.pratylenchus_brachyurus_status || "unknown"} onChange={(event) => updateRotation("pratylenchus_brachyurus_status", event.target.value)}>
            <option value="unknown">{t("Desconhecida / não analisada")}</option><option value="present">{t("Presente / confirmado")}</option><option value="not_detected">{t("Não detectado na análise")}</option>
          </select>
        </Field>
        <div className="settings-subtitle">{t("Outras observações")}</div>
        {(profile.pests || []).map((pest) => (
          <div className="settings-pest-row" key={pest.local_id}>
            <Field label={t("Nome científico ou identificação")} className="settings-pest-name">
              <input value={pest.pest_id} onChange={(event) => updatePest(pest.local_id, "pest_id", event.target.value)} placeholder={t("Ex.: ferrugem-asiática")} maxLength={100}/>
            </Field>
            <Field label={t("Situação")}>
              <select value={pest.status || "unknown"} onChange={(event) => updatePest(pest.local_id, "status", event.target.value)}><SelectOptions options={PEST_STATUS}/></select>
            </Field>
            <Field label={t("Severidade")}>
              <select value={pest.severity || "unknown"} onChange={(event) => updatePest(pest.local_id, "severity", event.target.value)}>
                <option value="unknown">{t("Desconhecida")}</option><option value="low">{t("Baixa")}</option><option value="moderate">{t("Moderada")}</option><option value="high">{t("Alta")}</option>
              </select>
            </Field>
            <Field label={t("Data da observação")}>
              <input type="date" value={pest.observed_date || ""} onChange={(event) => updatePest(pest.local_id, "observed_date", event.target.value)}/>
            </Field>
            <button className="settings-remove-button" type="button" onClick={() => removePest(pest.local_id)}>{t("Remover")}</button>
            <Field label={t("Observações")} className="settings-pest-notes">
              <input value={pest.notes || ""} onChange={(event) => updatePest(pest.local_id, "notes", event.target.value)} placeholder={t("Laudo, local da ocorrência, sintomas observados...")} maxLength={1000}/>
            </Field>
          </div>
        ))}
        <button type="button" className="settings-secondary-button" onClick={addPest}>{t("+ Adicionar observação fitossanitária")}</button>
      </Section>

      <Section icon={SlidersHorizontal} title={t("Preferências e objetivos do produtor")} description="Essas escolhas ajudam a ordenar as alternativas. Não substituem viabilidade técnica ou econômica.">
        <div className="settings-grid">
          <Field label={t("Objetivo principal para as culturas de transição")}>
            <select value={settings.preferences.objective || "balanced"} onChange={(event) => updatePreferences("objective", event.target.value)}>
              <option value="balanced">{t("Equilíbrio entre benefícios")}</option>
              <option value="ground_cover">{t("Priorizar cobertura do solo")}</option>
              <option value="nitrogen_cycling">{t("Priorizar ciclagem de nitrogênio")}</option>
              <option value="nematode_management">{t("Priorizar manejo de nematoides")}</option>
            </select>
          </Field>
          <Field label={t("Tolerância a riscos")}>
            <select value={settings.preferences.risk_tolerance || "medium"} onChange={(event) => updatePreferences("risk_tolerance", event.target.value)}>
              <option value="low">{t("Baixa — abordagem mais cautelosa")}</option><option value="medium">{t("Média")}</option><option value="high">{t("Alta — aceita avaliar mais alternativas")}</option>
            </select>
          </Field>
        </div>
        <div className="settings-subtitle">{t("O que é mais importante para você?")}</div>
        <div className="settings-priority-grid">
          {PRIORITIES.map((item) => (
            <label className="settings-priority-option" key={item.id}>
              <input type="checkbox" checked={priorities.includes(item.id)} onChange={() => togglePreference(item.id)}/>
              <span><strong>{t(item.label)}</strong><small>{t(item.hint)}</small></span>
            </label>
          ))}
        </div>
        <div className="settings-subtitle">{t("Culturas de transição que prefere não receber como sugestão")}</div>
        <div className="settings-check-grid">
          {TRANSITION_CROPS.map((crop) => (
            <label className="settings-check" key={crop.id}>
              <input type="checkbox" checked={avoidedCrops.includes(crop.id)} onChange={() => toggleAvoidCrop(crop.id)}/>
              <span>{t(crop.label)}</span>
            </label>
          ))}
        </div>
        <Field label={t("Observações e preferências adicionais")} hint={t("Ex.: evitar operações que exijam máquina não disponível; priorizar cobertura de baixo custo.")}>
          <textarea rows="3" maxLength={1500} value={settings.preferences.notes || ""} onChange={(event) => updatePreferences("notes", event.target.value)} placeholder={t("Descreva outras necessidades da propriedade...")}/>
        </Field>
      </Section>

      <section className="settings-section settings-actions-section">
        <div className="settings-actions">
          <button type="button" className="settings-save-button" onClick={save}><Save size={17}/> {t("Salvar configurações")}</button>
          <button type="button" className="settings-secondary-button" onClick={resetProfile}><RotateCcw size={16}/> {t("Restaurar este talhão")}</button>
          <button type="button" className="settings-secondary-button" onClick={exportSettings}><Download size={16}/> {t("Exportar JSON")}</button>
          <label className="settings-secondary-button settings-file-label"><Upload size={16}/> {t("Importar JSON")}<input type="file" accept="application/json,.json" onChange={importSettings}/></label>
        </div>
        {savedMessage && <p className="settings-success-message"><CheckCircle2 size={17}/>{t(savedMessage)}</p>}
        {formError && <p className="settings-error-message"><AlertTriangle size={17}/>{t(formError)}</p>}
        {importMessage && <p className={importMessage.startsWith("Não") ? "settings-error-message" : "settings-success-message"}>{t(importMessage)}</p>}
        <p className="settings-storage-note">{t("Os dados ficam neste navegador, no dispositivo em que foram salvos. Para compartilhar com a equipe ou mover para outro computador, use Exportar JSON. Ainda não existe login ou banco de dados multiusuário para sincronização automática.")}</p>
      </section>

      <section className="settings-section settings-api-section">
        <div className="settings-section-heading">
          <span className="settings-section-icon"><Wifi size={19}/></span>
          <div><h2>{t("Conexão com o backend")}</h2><p>{t("Verifique se a API está disponível antes de enviar as configurações.")}</p></div>
        </div>
        <div className="settings-api-status">
          {apiStatus.loading ? <><RefreshCw className="settings-spin" size={18}/> {t("Verificando conexão…")}</>
            : apiStatus.online ? <><CheckCircle2 size={18}/> API conectada em {api.baseUrl}</>
              : <><AlertTriangle size={18}/> API indisponível: {apiStatus.error}</>}
        </div>
        {apiStatus.sources.length > 0 && (
          <div className="settings-sources-grid">
            {apiStatus.sources.slice(0, 8).map((source) => (
              <div className="settings-source-item" key={source.name}>
                <span className={`settings-source-dot ${sourcePresentation(source).ready ? "is-ok" : "is-pending"}`}/>
                <div><strong>{source.name}</strong><small>{t(sourcePresentation(source).label)}</small></div>
              </div>
            ))}
          </div>
        )}
        <button type="button" className="settings-test-button" onClick={testApi} disabled={!apiStatus.online || testState.loading}>
          {testState.loading ? <><RefreshCw className="settings-spin" size={16}/> {t("Enviando…")}</> : <><Database size={16}/> {t("Testar configuração na API")}</>}
        </button>
        <p className="settings-storage-note">{t("O teste envia preferências, solo, manejo e rotação ao endpoint de recomendações. Nesta tela, os resultados dos modelos ambientais ainda não são calculados automaticamente; a API vai apontar os dados que faltam.")}</p>
        {testState.error && <div className="settings-api-error"><AlertTriangle size={17}/>{testState.error}</div>}
        {testState.result && (
          <div className="settings-api-result">
            <div className="settings-result-heading"><CheckCircle2 size={18}/><strong>{t("Configuração recebida pela API")}</strong><span>{testState.result.recommendations?.length || 0} recomendações geradas</span></div>
            {testState.result.recommendations?.map((item) => (
              <article className="settings-recommendation" key={item.id}>
                <div className="settings-recommendation-meta"><strong>{item.title}</strong><span className={`priority-${item.priority}`}>{item.priority === "high" ? "Alta" : item.priority === "medium" ? "Média" : "Baixa"}</span></div>
                <p>{item.recommended_action}</p>
                {item.why_this_was_recommended?.length > 0 && <small><strong>{t("Motivo:")}</strong> {item.why_this_was_recommended.join(" ")}</small>}
                {item.missing_data?.length > 0 && <small><strong>{t("Dados faltantes:")}</strong> {item.missing_data.join("; ")}</small>}
                {item.safeguards?.length > 0 && <small><strong>{t("Cuidados:")}</strong> {item.safeguards.join(" ")}</small>}
              </article>
            ))}
            {testState.result.data_gaps?.length > 0 && <div className="settings-data-gaps"><strong>{t("Informações que ainda faltam")}</strong><ul>{testState.result.data_gaps.map((item) => <li key={item}>{item}</li>)}</ul></div>}
            {testState.result.mandatory_review && <p className="settings-storage-note">{testState.result.mandatory_review}</p>}
          </div>
        )}
      </section>
    </div>
  );
}
