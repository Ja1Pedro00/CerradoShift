import { useI18n } from "../i18n";

import { useEffect, useState } from "react";
import { Link } from "react-router";
import {
  MapContainer,
  TileLayer,
  GeoJSON,
  useMap
} from "react-leaflet";
import L from "leaflet";

import "leaflet/dist/leaflet.css";
import "./MapPreview.css";

const STORAGE_KEY = "cerradoshift_talhoes";

function carregarTalhoes() {
  try {
    const dados = JSON.parse(localStorage.getItem(STORAGE_KEY));
    return Array.isArray(dados) ? dados : [];
  } catch {
    return [];
  }
}

function AjustarMapa({ talhoes }) {
  const map = useMap();

  useEffect(() => {
    if (talhoes.length === 0) return;

    const coordenadas = L.geoJSON({
      type: "FeatureCollection",
      features: talhoes.map(t => t.geojson)
    });

    const limites = coordenadas.getBounds();

    if (limites.isValid()) {
      map.fitBounds(limites, {
        padding: [25, 25],
        maxZoom: 16
      });
    }
  }, [map, talhoes]);

  return null;
}

export default function MapPreview() {
  const { t, tn, lang } = useI18n();
  const [talhoes, setTalhoes] = useState(carregarTalhoes);

  // Atualiza ao retornar à página
  useEffect(() => {
    setTalhoes(carregarTalhoes());
  }, []);

  const areaTotal = talhoes.reduce(
    (total, talhao) => total + (talhao.area || 0),
    0
  );

  return (
    <div className="map-preview">
      <div className="preview-header">
        <div>
          <h2>{t("Mapa da propriedade")}</h2>
          <p>
            {t("{n} talhão(ões) cadastrados", { n: talhoes.length })}
            {" · "}
            {areaTotal.toFixed(2)} {t("hectares")}
          </p>
        </div>

        <Link to="/mapa" className="preview-button">
          {t("Abrir mapa completo")}
        </Link>
      </div>

      <MapContainer
        center={[-18.9186, -48.2772]}
        zoom={12}
        zoomControl={false}
        scrollWheelZoom={false}
        doubleClickZoom={false}
        dragging={false}
        touchZoom={false}
        boxZoom={false}
        keyboard={false}
        style={{
          height: "320px",
          width: "100%",
          borderRadius: "10px"
        }}
      >
        <TileLayer
          attribution="Tiles &copy; Esri"
          url="https://services.arcgisonline.com/arcgis/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
          maxZoom={19}
        />

        {talhoes.map(talhao => (
          <GeoJSON
            key={`${talhao.id}-${lang}`}
            data={talhao.geojson}
            style={{
              color: "#4ade80",
              weight: 3,
              fillColor: "#16a34a",
              fillOpacity: 0.2
            }}
            onEachFeature={(feature, layer) => {
                const popup = L.DomUtil.create("div");
                const nome = L.DomUtil.create("strong", "", popup);
                const tamanho = L.DomUtil.create("p", "", popup);

                nome.textContent = tn(talhao.nome);
                tamanho.textContent =
                    `${Number(talhao.area).toFixed(2)} ${t("hectares")}`;

                layer.bindPopup(popup);
                }}
          />
        ))}

        <AjustarMapa talhoes={talhoes} />
      </MapContainer>

      {talhoes.length === 0 && (
        <p className="preview-empty">
          {t("Nenhum talhão cadastrado. Acesse o mapa completo para delimitar sua propriedade.")}
        </p>
      )}
    </div>
  );
}
