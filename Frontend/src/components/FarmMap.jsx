import { useI18n } from "../i18n";

import { useEffect, useState } from "react";
import L from "leaflet";
import {
  MapContainer,
  TileLayer,
  LayersControl,
  useMap
} from "react-leaflet";
import area from "@turf/area";

import "leaflet/dist/leaflet.css";
import "@geoman-io/leaflet-geoman-free";
import "@geoman-io/leaflet-geoman-free/dist/leaflet-geoman.css";

const STORAGE_KEY = "cerradoshift_talhoes";

function carregarTalhoes() {
  try {
    const dados = JSON.parse(localStorage.getItem(STORAGE_KEY));
    return Array.isArray(dados) ? dados : [];
  } catch {
    return [];
  }
}

function Ferramentas({ onAtualizar }) {
  const map = useMap();

  useEffect(() => {
    const grupo = L.featureGroup().addTo(map);

    // Restaura os talhões salvos anteriormente
    carregarTalhoes().forEach((talhao) => {
      const camada = L.geoJSON(talhao.geojson, {
        style: {
          color: "#087c56",
          weight: 3,
          fillOpacity: 0.2,
        },
      });

      camada.eachLayer((layer) => {
        layer.talhaoId = talhao.id;
        layer.bindPopup(talhao.nome);
        grupo.addLayer(layer);
      });
    });

    map.pm.addControls({
      position: "topleft",
      drawMarker: false,
      drawCircle: false,
      drawCircleMarker: false,
      drawPolyline: false,
      drawRectangle: false,
      drawText: false,
      drawPolygon: true,
      editMode: true,
      dragMode: false,
      cutPolygon: false,
      removalMode: true,
      rotateMode: false,
    });

    function atualizar() {
      const anteriores = carregarTalhoes();
      const resultado = [];

      grupo.eachLayer((layer) => {
        if (!layer.toGeoJSON) return;

        const geojson = layer.toGeoJSON();

        if (geojson.geometry.type !== "Polygon") return;

        let id = layer.talhaoId;

        if (!id) {
          id = crypto.randomUUID();
          layer.talhaoId = id;
        }

        const anterior = anteriores.find(t => t.id === id);

        resultado.push({
          id,
          nome: anterior?.nome || `Talhão ${resultado.length + 1}`,
          area: area(geojson) / 10000,
          geojson,
        });
      });

      localStorage.setItem(STORAGE_KEY, JSON.stringify(resultado));
      onAtualizar(resultado);
    }

    function aoCriar(evento) {
      grupo.addLayer(evento.layer);
      atualizar();
    }

    function aoEditar() {
      atualizar();
    }

    function aoRemover(evento) {
      if (grupo.hasLayer(evento.layer)) {
        grupo.removeLayer(evento.layer);
      }
      atualizar();
    }

    map.on("pm:create", aoCriar);
    map.on("pm:edit", aoEditar);
    map.on("pm:remove", aoRemover);

    onAtualizar(carregarTalhoes());

    return () => {
      map.off("pm:create", aoCriar);
      map.off("pm:edit", aoEditar);
      map.off("pm:remove", aoRemover);

      map.pm.removeControls();
      map.removeLayer(grupo);
    };
  }, [map, onAtualizar]);

  return null;
}

export default function FarmMap() {
  const { t, tn, lang } = useI18n();
  const [talhoes, setTalhoes] = useState(carregarTalhoes);
  function renomearTalhao(id) {
  const talhao = talhoes.find(t => t.id === id);

  if (!talhao) return;

  const novoNome = window.prompt(
    t("Digite o novo nome do talhão:"),
    talhao.nome
  );

  if (novoNome === null || !novoNome.trim()) return;

  const atualizados = talhoes.map(t =>
    t.id === id
      ? { ...t, nome: novoNome.trim() }
      : t
  );

  localStorage.setItem(
    "cerradoshift_talhoes",
    JSON.stringify(atualizados)
  );

  setTalhoes(atualizados);
}

  return (
    <div>
      <MapContainer
        center={[-18.9186, -48.2772]}
        zoom={12}
        style={{
          height: "500px",
          width: "100%",
          borderRadius: "12px",
        }}
      >
        <LayersControl key={lang} position="topright">
          <LayersControl.BaseLayer checked name={t("Mapa convencional")}>
            <TileLayer
              attribution="&copy; OpenStreetMap contributors"
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              maxZoom={19}
            />
          </LayersControl.BaseLayer>

          <LayersControl.BaseLayer name={t("Satélite")}>
            <TileLayer
              attribution="Tiles &copy; Esri"
              url="https://services.arcgisonline.com/arcgis/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
              maxZoom={19}
            />
          </LayersControl.BaseLayer>
        </LayersControl>

        <Ferramentas onAtualizar={setTalhoes} />
      </MapContainer>

      <div className="panel" style={{ marginTop: 20 }}>
        <h2>{t("Talhões cadastrados: {n}", { n: talhoes.length })}</h2>

        
{talhoes.map((talhao) => (
  <div
    key={talhao.id}
    className="talhao-item"
  >
    <div>
      <strong>{tn(talhao.nome)}</strong>
      <p>{talhao.area.toFixed(2)} {t("hectares")}</p>
    </div>

    <button
      className="talhao-rename"
      onClick={() => renomearTalhao(talhao.id)}
    >
      {t("Renomear")}
    </button>
  </div>
))}

      </div>
    </div>
  );
}
