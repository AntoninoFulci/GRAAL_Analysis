"use strict";
const data = JSON.parse(document.getElementById("report-data").textContent);
const byId = id => document.getElementById(id);
const node = (tag, text, className) => {
  const el = document.createElement(tag);
  if (text !== undefined) el.textContent = text;
  if (className) el.className = className;
  return el;
};
const link = (text, url, download = false) => {
  const el = node("a", text);
  el.href = url;
  if (download) el.setAttribute("download", "");
  return el;
};
const date = value => value ? new Intl.DateTimeFormat("it-IT", {
  dateStyle: "medium", timeStyle: "short", timeZone: "Europe/Rome"
}).format(new Date(value)) + " · Roma" : "Non attestata";
let current;
let limit = 18;
for (const report of data.campaigns) {
  const label = report.status === "historical" ? "Archivio" : report.mode === "production" ? "Produzione" : "Diagnostica";
  byId("campaign").append(new Option(`${report.id} · ${label}`, report.id));
}
byId("campaign").value = data.latest || data.campaigns[0].id;
byId("campaign-count").textContent = `${data.campaigns.length} campagne incluse · nessuna selezione basata sulla data dei file`;

function options(id, values, placeholder) {
  byId(id).replaceChildren(new Option(placeholder, ""));
  for (const value of [...new Set(values)].sort()) byId(id).append(new Option(value, value));
}

function renderCampaign() {
  current = data.campaigns.find(report => report.id === byId("campaign").value);
  const historical = current.status === "historical";
  const production = current.mode === "production";
  const latest = current.id === data.latest;
  byId("run-label").textContent = latest ? "ULTIMA PRODUZIONE COMPLETATA · TRA LE CAMPAGNE INCLUSE" : historical ? "ARCHIVIO STORICO" : production ? "PRODUZIONE PRECEDENTE" : "CAMPAGNA DIAGNOSTICA";
  byId("run-title").textContent = current.id;
  byId("run-status").textContent = historical ? "Completamento non attestato" : production ? "Esecuzione completata" : "Test data · completata";
  byId("run-status").className = `badge ${historical ? "historical" : production ? "" : "diagnostic"}`;
  byId("run-description").textContent = historical
    ? "Risultati preesistenti, esportati senza modificare gli originali. Data di completamento, configurazione e controlli della nuova pubblicazione non sono attestati."
    : "Report di una singola esecuzione. Il manifesto lega figure e metadati ai byte verificati al completamento degli stage richiesti.";
  const profiles = [...new Set(current.plots.map(plot => plot.profile))].join(" / ") || "—";
  const stats = [[current.plots.length, "Figure uniche"], [profiles, "Profili presenti"], [current.downloads.length, "Report e metadati"], [current.source_revision.slice(0, 8), "Revisione sorgente"]];
  byId("stats").replaceChildren(...stats.map(([value, label]) => {
    const el = node("div", undefined, "stat");
    el.append(node("strong", value), node("span", label));
    return el;
  }));
  byId("manifest-link").href = current.manifest_url;
  const fields = [["Completamento", date(current.completed_at)], ["Modalità", historical ? "Non attestata" : production ? "Produzione" : "Diagnostica / test_data"], ["Revisione", current.source_revision], ["Modifiche locali", current.source_dirty === null ? "Non registrate" : current.source_dirty ? "Presenti al completamento" : "Assenti al completamento"], ["Identità dei report", historical ? "Hash calcolati all’esportazione" : "SHA-256 verificati sul manifesto"]];
  byId("provenance-fields").replaceChildren(...fields.flatMap(([key, value]) => [node("dt", key), node("dd", value)]));
  byId("warnings").replaceChildren(...current.warnings.map(warning => node("li", String(warning))));
  byId("configuration").textContent = current.configuration ? JSON.stringify(current.configuration, null, 2) : "Configurazione effettiva non disponibile per questa campagna.";
  byId("configuration-note").textContent = current.configuration ? "Configurazione copiata dai metadati della campagna." : "Le opzioni non vengono ricostruite dai nomi dei file.";
  byId("downloads-title").textContent = `Report e metadati · ${current.downloads.length} file`;
  byId("downloads").replaceChildren(...current.downloads.map(file => {
    const el = node("li"); el.append(link(file.path, file.url, true)); return el;
  }));
  byId("search").value = "";
  options("profile", current.plots.map(p => p.profile), "Tutti i profili");
  options("category", current.plots.map(p => p.category), "Tutte le aree");
  limit = 18;
  renderGallery();
}

function renderGallery() {
  const term = byId("search").value.trim().toLocaleLowerCase("it");
  const profile = byId("profile").value;
  const category = byId("category").value;
  const plots = current.plots.filter(plot => (!profile || plot.profile === profile)
    && (!category || plot.category === category)
    && `${plot.title} ${plot.path} ${plot.aliases.join(" ")}`.toLocaleLowerCase("it").includes(term));
  byId("plot-count").textContent = `${plots.length} figure trovate · ${Math.min(limit, plots.length)} mostrate`;
  byId("gallery").replaceChildren(...plots.slice(0, limit).map(plot => {
    const card = node("article", undefined, "plot-card");
    const preview = link("", plot.url);
    preview.className = "plot-preview";
    preview.setAttribute("aria-label", `Apri originale: ${plot.title}, ${plot.profile}`);
    if (plot.preview) {
      const img = node("img"); img.src = plot.preview; img.alt = `Anteprima: ${plot.title}`;
      img.loading = "lazy"; img.decoding = "async"; preview.append(img);
    } else preview.append(node("span", "Apri figura ↗", "pdf-placeholder"));
    const body = node("div", undefined, "plot-body");
    const tags = node("div", undefined, "plot-tags");
    tags.append(node("span", plot.profile), node("span", plot.category));
    const actions = node("div", undefined, "plot-actions");
    actions.append(link("Apri originale ↗", plot.url), link("Scarica ↘", plot.url, true));
    body.append(tags, node("h3", plot.title), node("p", plot.path, "plot-path"), actions);
    if (plot.aliases.length) body.append(node("p", `${plot.aliases.length} copie identiche incluse nel manifesto`, "plot-path"));
    card.append(preview, body);
    return card;
  }));
  byId("empty").hidden = plots.length !== 0;
  byId("more").hidden = plots.length <= limit;
}

byId("campaign").addEventListener("change", renderCampaign);
byId("filters").addEventListener("submit", event => event.preventDefault());
byId("filters").addEventListener("input", () => { limit = 18; renderGallery(); });
byId("filters").addEventListener("reset", () => {
  byId("search").value = ""; byId("profile").value = ""; byId("category").value = "";
  limit = 18; renderGallery();
});
byId("more").addEventListener("click", () => { limit += 18; renderGallery(); });
byId("docs").replaceChildren(...data.docs.map(doc => {
  const card = node("article", undefined, "doc-card");
  card.append(link(`${doc.title} ↗`, doc.url), link("Copia Markdown della pubblicazione ↘", doc.download, true));
  return card;
}));
byId("build-info").textContent = `Portale generato ${date(data.generated_at)} · documentazione ${data.documentation_revision.source_revision.slice(0, 8)}`;
renderCampaign();
