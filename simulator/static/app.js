/**
 * Battery Thermal Runaway Workbench - CAE Mühendislik Platformu İstemci Kodu
 */

// Global Uygulama Durumu (State)
const state = {
  activeTreePanel: "geometry",
  selectedCellId: 0,
  viewMode: "3d", // '3d', '2d', 'heatmap'
  showLabels: true,
  simulationData: null,
  currentStepIndex: 0,
  isPlaying: false,
  playbackSpeed: 1.0,
  animationTimer: null,
  tempChart: null,
  loadedChemistries: {},
  loadedMaterials: {},
  loadedFormats: {}
};

document.addEventListener("DOMContentLoaded", () => {
  initTreeNavigation();
  initFormBindings();
  initViewerControls();
  initTimeline();
  initModals();
  loadLibraries().then(() => {
    updatePackLayoutFromInputs();
    updateChemistryDetails();
  });
});

/* ================= 1. KÜTÜPHANE YÜKLEME VE API ================= */

async function loadLibraries() {
  try {
    // 1. Hücre Kimyaları
    const chemRes = await fetch("/api/chemistry/library");
    if (chemRes.ok) {
      const chemData = await chemRes.json();
      const chemSelect = document.getElementById("selectChemistry");
      const curVal = chemSelect.value;
      chemSelect.innerHTML = "";
      state.loadedChemistries = {};
      chemData.chemistries.forEach(c => {
        state.loadedChemistries[c.chemistry_id] = c;
        const isCustom = c.source_type === "user_defined" ? " 🛠️ (Özel)" : "";
        const onset = c.T_onset_C || (c.T_onset_K - 273.15).toFixed(0);
        chemSelect.innerHTML += `<option value="${c.chemistry_id}">${c.name}${isCustom} (${onset}°C Onset)</option>`;
      });
      if (curVal && state.loadedChemistries[curVal]) {
        chemSelect.value = curVal;
      }
    }

    // 2. Malzemeler ve Bariyerler
    const matRes = await fetch("/api/materials/library");
    if (matRes.ok) {
      const matData = await matRes.json();
      const sepSelect = document.getElementById("selectSeparator");
      const gapSelect = document.getElementById("selectGapMaterial");
      const curSep = sepSelect.value;
      const curGap = gapSelect.value;

      sepSelect.innerHTML = '<option value="" selected>Yok (Sadece Boşluk/Dolgu)</option>';
      gapSelect.innerHTML = "";
      state.loadedMaterials = matData;

      Object.keys(matData).forEach(key => {
        const m = matData[key];
        const isCustom = m.source_type === "user_defined" ? " 🛠️ (Özel)" : "";
        const optHtml = `<option value="${key}">${m.name || key}${isCustom} (${m.k_thermal_W_per_m_K} W/mK)</option>`;
        sepSelect.innerHTML += optHtml;
        gapSelect.innerHTML += optHtml;
      });

      if (curSep && matData[curSep]) sepSelect.value = curSep;
      if (curGap && matData[curGap]) gapSelect.value = curGap;
      else if (gapSelect.querySelector('option[value="air_gap"]')) gapSelect.value = "air_gap";
    }

    // 3. Hücre Formatları
    const fmtRes = await fetch("/api/formats/library");
    if (fmtRes.ok) {
      const fmtData = await fmtRes.json();
      const fmtSelect = document.getElementById("selectFormat");
      const curFmt = fmtSelect.value;
      fmtSelect.innerHTML = "";
      state.loadedFormats = fmtData;

      Object.keys(fmtData).forEach(key => {
        const f = fmtData[key];
        const isCustom = f.source_type === "user_defined" ? " 🛠️ (Özel)" : "";
        const desc = f.type === "prismatic"
          ? `${Math.round(f.width * 1000)}x${Math.round(f.height * 1000)} mm`
          : `${Math.round(f.radius * 2000)}x${Math.round(f.height * 1000)} mm`;
        fmtSelect.innerHTML += `<option value="${key}">${key}${isCustom} (${desc})</option>`;
      });

      if (curFmt && fmtData[curFmt]) fmtSelect.value = curFmt;
    }
  } catch (err) {
    console.error("Kütüphaneler yüklenirken hata oluştu:", err);
  }
}

/* ================= 2. PROJE AĞACI VE SAĞ PANEL NAVİGASYONU ================= */

function initTreeNavigation() {
  const treeItems = document.querySelectorAll(".tree-item");
  treeItems.forEach(item => {
    item.addEventListener("click", () => {
      const panelName = item.dataset.panel;
      switchTreePanel(panelName);
    });
  });
}

function switchTreePanel(panelName) {
  state.activeTreePanel = panelName;

  // Sol ağaçtaki aktif sınıfı güncelle
  document.querySelectorAll(".tree-item").forEach(el => {
    el.classList.remove("active");
  });
  const targetItem = document.querySelector(`.tree-item[data-panel="${panelName}"]`);
  if (targetItem) targetItem.classList.add("active");

  // Sağ panel başlığı ve içerik bölümlerini değiştir
  const titleEl = document.getElementById("propertiesTitle");
  const badgeEl = document.getElementById("propertiesBadge");

  // Tüm alt panel bölümlerini gizle
  const sections = [
    "panelGeometry", "panelChemistry", "panelAdvPhysics", "panelThermal", "panelCooling",
    "panelExcitation", "panelSimulation", "panelDesignStudy", "panelResults", "panelCellInspector"
  ];
  sections.forEach(id => {
    const el = document.getElementById(id);
    if (el) el.style.display = "none";
  });

  switch (panelName) {
    case "geometry":
      titleEl.textContent = "GEOMETRİ VE DİZİLİM";
      badgeEl.textContent = "MODEL";
      document.getElementById("panelGeometry").style.display = "block";
      break;
    case "chemistry":
      titleEl.textContent = "HÜCRE KİMYASI VE KİNETİK";
      badgeEl.textContent = "MODEL";
      document.getElementById("panelChemistry").style.display = "block";
      updateChemistryDetails();
      break;
    case "adv_physics":
      titleEl.textContent = "GELİŞMİŞ FİZİK (KİNETİK & VENTING)";
      badgeEl.textContent = "MODEL";
      document.getElementById("panelAdvPhysics").style.display = "block";
      break;
    case "thermal":
      titleEl.textContent = "TERMAL PARAMETRELER & BARİYER";
      badgeEl.textContent = "MODEL";
      document.getElementById("panelThermal").style.display = "block";
      break;
    case "cooling":
      titleEl.textContent = "SOĞUTMA SİSTEMİ (COLD PLATE)";
      badgeEl.textContent = "MODEL";
      document.getElementById("panelCooling").style.display = "block";
      break;
    case "excitation":
      titleEl.textContent = "ABUSE VE TETİKLEME";
      badgeEl.textContent = "MODEL";
      document.getElementById("panelExcitation").style.display = "block";
      break;
    case "simulation":
      titleEl.textContent = "ÇÖZÜCÜ VE ZAMAN AYARLARI";
      badgeEl.textContent = "ÇÖZÜM";
      document.getElementById("panelSimulation").style.display = "block";
      break;
    case "design_study":
      titleEl.textContent = "TASARIM ÇALIŞMASI (PARAMETRE TARAMASI)";
      badgeEl.textContent = "OPTİMİZASYON";
      document.getElementById("panelDesignStudy").style.display = "block";
      break;
    case "results":
      titleEl.textContent = "SONUÇLAR VE UL 9540A RAPORU";
      badgeEl.textContent = "POST-PROCESS";
      document.getElementById("panelResults").style.display = "block";
      break;
    case "cell_inspector":
      titleEl.textContent = `HÜCRE #${state.selectedCellId} İNCELEME`;
      badgeEl.textContent = "BİLEŞEN";
      document.getElementById("panelCellInspector").style.display = "block";
      updateCellInspectorUI();
      break;
  }
}

/* ================= 3. PARAMETRE BAĞLANTILARI (FORM BINDINGS) ================= */

function initFormBindings() {
  // Simülasyon süresi slider'ı
  const simTimeSlider = document.getElementById("inputSimTime");
  const simTimeLabel = document.getElementById("lblSimTime");
  const lblTotalTime = document.getElementById("lblTotalTime");
  simTimeSlider.addEventListener("input", (e) => {
    simTimeLabel.textContent = `${e.target.value} s`;
    lblTotalTime.textContent = `${parseFloat(e.target.value).toFixed(2)} s`;
  });

  // Soğutma toggle
  const chkCooling = document.getElementById("checkboxCooling");
  const coolingOpts = document.getElementById("coolingOptions");
  const statusCoolingBadge = document.getElementById("statusCoolingBadge");
  chkCooling.addEventListener("change", (e) => {
    coolingOpts.style.display = e.target.checked ? "block" : "none";
    statusCoolingBadge.textContent = e.target.checked ? "✓" : "○";
    statusCoolingBadge.className = e.target.checked ? "tree-status status-ready" : "tree-status";
  });

  // Tetikleme tipi toggle (Thermal pulse vs Instant onset)
  const selectTrigger = document.getElementById("selectTriggerMethod");
  const groupThermalPulse = document.getElementById("groupThermalPulse");
  const groupInstantOnset = document.getElementById("groupInstantOnset");
  selectTrigger.addEventListener("change", (e) => {
    const isInstant = e.target.value === "instant_onset";
    groupThermalPulse.style.display = isInstant ? "none" : "grid";
    groupInstantOnset.style.display = isInstant ? "block" : "none";
  });

  // Geometri değişiklikleri (Satır, Sütun, Boşluk, Staggered, Format)
  ["inputRows", "inputCols", "inputSpacingX", "inputSpacingY", "checkboxStaggered", "selectFormat"].forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.addEventListener("input", updatePackLayoutFromInputs);
      el.addEventListener("change", updatePackLayoutFromInputs);
    }
  });

  // Kimya değişimi
  document.getElementById("selectChemistry").addEventListener("change", () => {
    updateChemistryDetails();
    if (document.getElementById("checkboxAdvPhysics")?.checked) {
      prefillAdvPhysicsFields();
    }
  });

  // Gelişmiş Fizik toggle
  const chkAdvPhysics = document.getElementById("checkboxAdvPhysics");
  const advFields = document.getElementById("advPhysicsFields");
  const statusAdvBadge = document.getElementById("statusAdvPhysicsBadge");
  if (chkAdvPhysics && advFields) {
    chkAdvPhysics.addEventListener("change", (e) => {
      if (e.target.checked) {
        advFields.classList.add("active");
        if (statusAdvBadge) {
          statusAdvBadge.textContent = "✓";
          statusAdvBadge.className = "tree-status status-ready";
        }
        prefillAdvPhysicsFields();
      } else {
        advFields.classList.remove("active");
        if (statusAdvBadge) {
          statusAdvBadge.textContent = "○";
          statusAdvBadge.className = "tree-status";
        }
      }
    });
  }

  // Tasarım Çalışması (Design Study) tür değişimi ve çalıştırma
  const selectSweep = document.getElementById("selectSweepType");
  if (selectSweep) {
    selectSweep.addEventListener("change", updateSweepPills);
  }

  const btnStudy = document.getElementById("btnRunDesignStudy");
  if (btnStudy) {
    btnStudy.addEventListener("click", handleRunDesignStudy);
  }

  // Tetikleyici hücre değişimi
  document.getElementById("inputTriggerCell").addEventListener("input", () => {
    updateCellStyles();
    draw2DCanvas();
  });

  // Seçili hücreyi tetikleyici yap butonu
  document.getElementById("btnSetAsTriggerCell").addEventListener("click", () => {
    document.getElementById("inputTriggerCell").value = state.selectedCellId;
    updateCellInspectorUI();
    updateCellStyles();
    draw2DCanvas();
  });

  // Simülasyonu Çalıştır butonları (Header & Sidebar)
  document.getElementById("btnTopRunSim").addEventListener("click", runSimulation);
  document.getElementById("btnSideRunSim").addEventListener("click", runSimulation);
  document.getElementById("simConfigForm").addEventListener("submit", (e) => {
    e.preventDefault();
    runSimulation();
  });
}

function updateChemistryDetails() {
  const chemId = document.getElementById("selectChemistry").value;
  const chem = state.loadedChemistries[chemId];
  if (!chem) return;

  const onset = chem.T_onset_C || (chem.T_onset_K - 273.15).toFixed(0);
  const trigger = chem.T_trigger_C || (chem.T_trigger_K - 273.15).toFixed(0);
  const ea = chem.Ea_kJ_per_mol || (chem.Ea_J_per_mol / 1000).toFixed(1);

  document.getElementById("chemValOnset").textContent = `${onset} °C`;
  document.getElementById("chemValTrigger").textContent = `${trigger} °C`;
  document.getElementById("chemValDeltaH").textContent = `${chem.delta_H_J_per_g} J/g`;
  document.getElementById("chemValEa").textContent = `${ea} kJ/mol`;

  // Proje başlığı etiketini güncelle
  const fmt = document.getElementById("selectFormat").value;
  document.getElementById("projectTitle").textContent = `${fmt} / ${chem.name || chemId} Modülü`;
}

/* ================= 4. 3D VE 2D VİZUALİZASYON MOTORU ================= */

function initViewerControls() {
  const btn3D = document.getElementById("btnView3D");
  const btn2D = document.getElementById("btnView2D");
  const btnHeatmap = document.getElementById("btnViewHeatmap");
  const viewer3D = document.getElementById("battery3DViewer");
  const viewer2D = document.getElementById("battery2DViewer");

  btn3D.addEventListener("click", () => {
    state.viewMode = "3d";
    btn3D.classList.add("active");
    btn2D.classList.remove("active");
    btnHeatmap.classList.remove("active");
    viewer3D.style.display = "flex";
    viewer2D.style.display = "none";
  });

  btn2D.addEventListener("click", () => {
    state.viewMode = "2d";
    btn2D.classList.add("active");
    btn3D.classList.remove("active");
    btnHeatmap.classList.remove("active");
    viewer3D.style.display = "none";
    viewer2D.style.display = "flex";
    draw2DCanvas();
  });

  btnHeatmap.addEventListener("click", () => {
    state.viewMode = "heatmap";
    btnHeatmap.classList.add("active");
    btn3D.classList.remove("active");
    btn2D.classList.remove("active");
    viewer3D.style.display = "none";
    viewer2D.style.display = "flex";
    draw2DCanvas();
  });

  document.getElementById("btnResetView").addEventListener("click", () => {
    const stage = document.getElementById("pack3dStage");
    stage.style.transform = "rotateX(28deg) rotateZ(-8deg)";
  });

  document.getElementById("btnToggleLabels").addEventListener("click", () => {
    state.showLabels = !state.showLabels;
    updateCellStyles();
    draw2DCanvas();
  });
}

function updatePackLayoutFromInputs() {
  const rows = parseInt(document.getElementById("inputRows").value, 10) || 3;
  const cols = parseInt(document.getElementById("inputCols").value, 10) || 3;
  const spacingX = parseFloat(document.getElementById("inputSpacingX").value) || 2.0;
  const spacingY = parseFloat(document.getElementById("inputSpacingY").value) || 2.0;
  const staggered = document.getElementById("checkboxStaggered").checked;
  const format = document.getElementById("selectFormat").value;

  const totalCells = rows * cols;
  document.getElementById("calcTotalCells").textContent = `${totalCells} Hücre (${rows}x${cols})`;
  document.getElementById("viewerPackStats").textContent = `${rows}x${cols} (${totalCells} Hücre) • ${format}`;

  // Kaba boyut tahmini
  let cellDiam = 18;
  if (format === "21700") cellDiam = 21;
  else if (format === "4680") cellDiam = 46;
  else if (format === "prismatic") cellDiam = 148;

  const packW = Math.round(cols * cellDiam + (cols - 1) * spacingX);
  const packH = Math.round(rows * cellDiam + (rows - 1) * spacingY);
  document.getElementById("calcPackDims").textContent = `~${packW} x ${packH} mm`;

  // Tetikleyici sınır kontrolü
  const triggerInput = document.getElementById("inputTriggerCell");
  if (parseInt(triggerInput.value, 10) >= totalCells) {
    triggerInput.value = 0;
  }
  triggerInput.max = totalCells - 1;

  // 3D Hücre Sahnesi Oluştur
  render3DStage(rows, cols, staggered, format);
  draw2DCanvas();
}

function render3DStage(rows, cols, staggered, format) {
  const stage = document.getElementById("pack3dStage");
  stage.innerHTML = "";
  stage.style.gridTemplateColumns = `repeat(${cols}, 54px)`;

  const totalCells = rows * cols;
  const triggerCellId = parseInt(document.getElementById("inputTriggerCell").value, 10);

  for (let id = 0; id < totalCells; id++) {
    const row = Math.floor(id / cols);
    const col = id % cols;

    const cell = document.createElement("div");
    cell.className = "cell-3d";
    cell.dataset.id = id;

    if (id === triggerCellId) cell.classList.add("trigger");
    if (id === state.selectedCellId) cell.classList.add("selected");

    // Staggered girinti
    if (staggered && row % 2 === 1) {
      cell.style.transform = "translateX(27px)";
    }

    cell.innerHTML = `
      <div class="cell-cap"></div>
      <div class="cell-id-tag">#${id}</div>
      <div class="cell-temp-tag" id="tempTag3D_${id}">25°C</div>
    `;

    cell.addEventListener("click", (e) => {
      e.stopPropagation();
      selectCell(id);
    });

    stage.appendChild(cell);
  }
}

function selectCell(id) {
  state.selectedCellId = id;

  // Sol ağaçtaki "SEÇİLİ BİLEŞEN" sekmesini aktif göster
  const treeSection = document.getElementById("treeSectionCellInspector");
  const treeLabel = document.getElementById("treeLabelCellInspector");
  treeSection.style.display = "block";
  treeLabel.textContent = `Hücre #${id} İnceleme`;

  switchTreePanel("cell_inspector");

  // 3D Seçim Vurgusu
  document.querySelectorAll(".cell-3d").forEach(c => {
    c.classList.toggle("selected", parseInt(c.dataset.id, 10) === id);
  });

  updateCellInspectorUI();
  draw2DCanvas();
}

function updateCellInspectorUI() {
  const id = state.selectedCellId;
  const triggerId = parseInt(document.getElementById("inputTriggerCell").value, 10);
  const isTrigger = id === triggerId;

  document.getElementById("inspectCellName").textContent = `Hücre #${id}`;
  document.getElementById("inspectCellIsTrigger").textContent = isTrigger ? "EVET (TETİKLEYİCİ)" : "HAYIR";
  document.getElementById("inspectCellIsTrigger").style.color = isTrigger ? "#ef4444" : "#cbd5e1";

  const fmt = document.getElementById("selectFormat").value;
  document.getElementById("inspectCellFormat").textContent = fmt;

  // Simülasyon verisi varsa anlık değerleri yaz
  if (state.simulationData) {
    const simRes = state.simulationData.simulation_result;
    const stepIdx = state.currentStepIndex;
    const timeSec = simRes.time_points_s[stepIdx];
    const temp = simRes.temperature_history_C[id] ? simRes.temperature_history_C[id][stepIdx] : 25.0;
    const alpha = simRes.alpha_history[id] ? simRes.alpha_history[id][stepIdx] : 0.0;
    const summary = simRes.cell_summaries[id];

    document.getElementById("inspectTimeSec").textContent = timeSec.toFixed(2);
    document.getElementById("inspectCellTemp").textContent = `${temp.toFixed(1)} °C`;
    document.getElementById("inspectCellAlpha").textContent = alpha.toFixed(3);

    if (summary) {
      document.getElementById("inspectCellMaxTemp").textContent = `${summary.max_temperature_C.toFixed(1)} °C`;
      document.getElementById("inspectCellRunawayTime").textContent = summary.runaway_time_s != null ? `${summary.runaway_time_s.toFixed(2)} s` : "Yayılmadı";
      document.getElementById("inspectCellCoords").textContent = `X: ${summary.pos_x_mm.toFixed(1)} mm, Y: ${summary.pos_y_mm.toFixed(1)} mm`;
      document.getElementById("inspectCellMass").textContent = `${(summary.mass_kg * 1000).toFixed(1)} g`;
    }

    // Durum etiketi
    const statusTag = document.getElementById("inspectCellStatus");
    if (alpha >= 0.99) {
      statusTag.textContent = "TÜKENDİ (BURNED)";
      statusTag.style.color = "#94a3b8";
    } else if (temp >= 210) {
      statusTag.textContent = "TERMAL KAÇAK (RUNAWAY)";
      statusTag.style.color = "#ef4444";
    } else if (temp >= 155) {
      statusTag.textContent = "ONSET (EKZOTERMİK)";
      statusTag.style.color = "#f97316";
    } else if (temp >= 60) {
      statusTag.textContent = "ISINMA (WARMING)";
      statusTag.style.color = "#eab308";
    } else {
      statusTag.textContent = "NORMAL (GÜVENLİ)";
      statusTag.style.color = "#10b981";
    }
  } else {
    document.getElementById("inspectTimeSec").textContent = "0.00";
    document.getElementById("inspectCellTemp").textContent = "25.0 °C";
    document.getElementById("inspectCellAlpha").textContent = "0.000";
    document.getElementById("inspectCellMaxTemp").textContent = "-- °C";
    document.getElementById("inspectCellRunawayTime").textContent = "-- s";
    document.getElementById("inspectCellStatus").textContent = "NORMAL";
  }
}

function getTemperatureColor(tempC, alpha) {
  if (alpha >= 0.99) return "#475569"; // Burned out
  if (tempC >= 210) return "#dc2626";  // Runaway
  if (tempC >= 155) return "#f97316";  // Onset
  if (tempC >= 60) return "#eab308";   // Warming
  return "#2563eb";                    // Normal cool
}

function updateCellStyles() {
  const triggerCellId = parseInt(document.getElementById("inputTriggerCell").value, 10);
  const totalCells = parseInt(document.getElementById("inputRows").value, 10) * parseInt(document.getElementById("inputCols").value, 10);

  for (let id = 0; id < totalCells; id++) {
    const cellEl = document.querySelector(`.cell-3d[data-id="${id}"]`);
    if (!cellEl) continue;

    cellEl.classList.toggle("trigger", id === triggerCellId);
    cellEl.classList.toggle("selected", id === state.selectedCellId);

    const tempTag = document.getElementById(`tempTag3D_${id}`);

    if (state.simulationData) {
      const simRes = state.simulationData.simulation_result;
      const step = state.currentStepIndex;
      const temp = simRes.temperature_history_C[id] ? simRes.temperature_history_C[id][step] : 25.0;
      const alpha = simRes.alpha_history[id] ? simRes.alpha_history[id][step] : 0.0;

      if (tempTag) {
        tempTag.textContent = state.showLabels ? `${Math.round(temp)}°C` : "";
      }

      // Durum sınıflarını temizle
      cellEl.classList.remove("warming", "onset", "runaway", "burned");

      if (alpha >= 0.99) cellEl.classList.add("burned");
      else if (temp >= 210) cellEl.classList.add("runaway");
      else if (temp >= 155) cellEl.classList.add("onset");
      else if (temp >= 60) cellEl.classList.add("warming");
    } else {
      if (tempTag) tempTag.textContent = state.showLabels ? "25°C" : "";
      cellEl.classList.remove("warming", "onset", "runaway", "burned");
    }
  }
}

function draw2DCanvas() {
  const canvas = document.getElementById("packCanvas");
  if (!canvas || state.viewMode === "3d") return;

  const ctx = canvas.getContext("2d");
  ctx.fillStyle = "#0b0f15";
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  const rows = parseInt(document.getElementById("inputRows").value, 10) || 3;
  const cols = parseInt(document.getElementById("inputCols").value, 10) || 3;
  const staggered = document.getElementById("checkboxStaggered").checked;
  const triggerCellId = parseInt(document.getElementById("inputTriggerCell").value, 10);

  const marginX = 80;
  const marginY = 60;
  const availableW = canvas.width - marginX * 2;
  const availableH = canvas.height - marginY * 2;

  const pitchX = availableW / Math.max(1, cols - 1 || 1);
  const pitchY = availableH / Math.max(1, rows - 1 || 1);
  const radius = Math.min(24, Math.min(pitchX, pitchY) * 0.35);

  const cellCoords = {};

  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const id = r * cols + c;
      const offsetX = (staggered && r % 2 === 1) ? pitchX * 0.5 : 0;
      const x = marginX + c * pitchX + offsetX;
      const y = marginY + r * pitchY;
      cellCoords[id] = { x, y };
    }
  }

  // 1. Hücreler arası iletim bağlarını çiz
  ctx.strokeStyle = "#1e293b";
  ctx.lineWidth = 2;
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const id = r * cols + c;
      // Sağ komşu
      if (c + 1 < cols) {
        const rightId = r * cols + (c + 1);
        ctx.beginPath();
        ctx.moveTo(cellCoords[id].x, cellCoords[id].y);
        ctx.lineTo(cellCoords[rightId].x, cellCoords[rightId].y);
        ctx.stroke();
      }
      // Alt komşu
      if (r + 1 < rows) {
        const bottomId = (r + 1) * cols + c;
        ctx.beginPath();
        ctx.moveTo(cellCoords[id].x, cellCoords[id].y);
        ctx.lineTo(cellCoords[bottomId].x, cellCoords[bottomId].y);
        ctx.stroke();
      }
    }
  }

  // 2. Yayılım grafiği (Propagation vector lines)
  if (state.simulationData) {
    const simRes = state.simulationData.simulation_result;
    const timeSec = simRes.time_points_s[state.currentStepIndex];
    const pathGraph = state.simulationData.evaluation.propagation_path_graph || [];

    pathGraph.forEach(edge => {
      const fromCoord = cellCoords[edge.from_cell_id];
      const toCoord = cellCoords[edge.to_cell_id];
      const fromSummary = simRes.cell_summaries[edge.from_cell_id];
      const toSummary = simRes.cell_summaries[edge.to_cell_id];

      if (fromCoord && toCoord && fromSummary.runaway_time_s <= timeSec && toSummary.runaway_time_s <= timeSec) {
        ctx.beginPath();
        ctx.moveTo(fromCoord.x, fromCoord.y);
        ctx.lineTo(toCoord.x, toCoord.y);
        ctx.strokeStyle = "#ef4444";
        ctx.lineWidth = 3;
        ctx.setLineDash([6, 4]);
        ctx.stroke();
        ctx.setLineDash([]);
      }
    });
  }

  // 3. Hücreleri çiz
  Object.keys(cellCoords).forEach(idStr => {
    const id = parseInt(idStr, 10);
    const coord = cellCoords[id];

    let temp = 25.0;
    let alpha = 0.0;
    if (state.simulationData) {
      const simRes = state.simulationData.simulation_result;
      const step = state.currentStepIndex;
      temp = simRes.temperature_history_C[id] ? simRes.temperature_history_C[id][step] : 25.0;
      alpha = simRes.alpha_history[id] ? simRes.alpha_history[id][step] : 0.0;
    }

    const fillColor = getTemperatureColor(temp, alpha);

    // Runaway parlaması
    if (temp >= 210) {
      ctx.beginPath();
      ctx.arc(coord.x, coord.y, radius + 8, 0, 2 * Math.PI);
      ctx.fillStyle = "rgba(239, 68, 68, 0.25)";
      ctx.fill();
    }

    // Hücre dairesi
    ctx.beginPath();
    ctx.arc(coord.x, coord.y, radius, 0, 2 * Math.PI);
    ctx.fillStyle = fillColor;
    ctx.fill();

    // Çerçeve (Tetikleyici vs Seçili vs Normal)
    if (id === state.selectedCellId) {
      ctx.strokeStyle = "#38bdf8";
      ctx.lineWidth = 3;
    } else if (id === triggerCellId) {
      ctx.strokeStyle = "#f43f5e";
      ctx.lineWidth = 2.5;
    } else {
      ctx.strokeStyle = "rgba(255, 255, 255, 0.2)";
      ctx.lineWidth = 1.5;
    }
    ctx.stroke();

    // Etiketler
    if (state.showLabels) {
      ctx.fillStyle = "#ffffff";
      ctx.font = "bold 9px sans-serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(`#${id}`, coord.x, coord.y - 4);

      ctx.font = "bold 10px sans-serif";
      ctx.fillText(`${Math.round(temp)}°`, coord.x, coord.y + 7);
    }
  });
}

/* ================= 5. SİMÜLASYON YÜRÜTME VE ÇÖZÜCÜ (SOLVER) ================= */

function prefillAdvPhysicsFields() {
  const chemId = document.getElementById("selectChemistry").value;
  const chem = state.loadedChemistries[chemId];
  if (!chem) return;

  const fA = document.getElementById("inputAdvA");
  const fEa = document.getElementById("inputAdvEa");
  const fdH = document.getElementById("inputAdvDeltaH");
  const fRatio = document.getElementById("inputAdvRatio");

  if (!fA.value) fA.value = chem.A_pre_exponential_per_s || "2.5e12";
  if (!fEa.value) fEa.value = chem.Ea_J_per_mol || "128500";
  if (!fdH.value) fdH.value = chem.delta_H_J_per_g || "780";
  if (!fRatio.value) fRatio.value = chem.active_mass_ratio || "0.58";
}

function updateSweepPills() {
  const sweepType = document.getElementById("selectSweepType")?.value || "spacing_sweep";
  const container = document.getElementById("sweepPillsContainer");
  if (!container) return;

  container.innerHTML = "";
  let pills = [];
  if (sweepType === "spacing_sweep") {
    pills = ["1.5 mm", "2.0 mm", "2.5 mm", "3.0 mm"];
  } else if (sweepType === "separator_sweep") {
    pills = ["Bariyersiz (Hava)", "Mika (0.5 mm)", "Mika (1.0 mm)", "Aerojel (1.0 mm)"];
  } else if (sweepType === "cooling_sweep") {
    pills = ["Pasif (Kapalı)", "h = 400 W/m²K", "h = 800 W/m²K", "h = 1500 W/m²K"];
  }

  pills.forEach(p => {
    const span = document.createElement("span");
    span.className = "event-pill";
    span.textContent = p;
    container.appendChild(span);
  });
}

function buildSimulationPayload() {
  const form = document.getElementById("simConfigForm");
  const formData = new FormData(form);

  const advEnabled = document.getElementById("checkboxAdvPhysics")?.checked || false;

  return {
    rows: parseInt(formData.get("rows"), 10),
    cols: parseInt(formData.get("cols"), 10),
    cell_format: formData.get("cell_format"),
    spacing_x_mm: parseFloat(formData.get("spacing_x_mm")),
    spacing_y_mm: parseFloat(formData.get("spacing_y_mm")),
    staggered: formData.get("staggered") === "on",
    chemistry_id: formData.get("chemistry_id"),
    separator_material_id: formData.get("separator_material_id") || null,
    separator_thickness_mm: parseFloat(formData.get("separator_thickness_mm") || 0),
    gap_material_id: formData.get("gap_material_id") || "air_gap",
    T_ambient_C: parseFloat(formData.get("T_ambient_C")),
    busbar_conductance_W_per_K: parseFloat(formData.get("busbar_conductance_W_per_K") || 0.6),
    active_cooling_enabled: formData.get("active_cooling_enabled") === "on",
    h_cooling_plate_W_per_m2_K: parseFloat(formData.get("h_cooling_plate_W_per_m2_K") || 800),
    T_coolant_C: parseFloat(formData.get("T_coolant_C") || 25),
    trigger_cell_id: parseInt(formData.get("trigger_cell_id"), 10),
    trigger_method: formData.get("trigger_method"),
    trigger_power_W: parseFloat(formData.get("trigger_power_W")),
    trigger_duration_s: parseFloat(formData.get("trigger_duration_s")),
    trigger_initial_temp_C: parseFloat(formData.get("trigger_initial_temp_C") || 250.0),
    simulation_time_s: parseFloat(formData.get("simulation_time_s")),
    num_output_points: 200,

    // Gelişmiş Fizik
    advanced_physics_enabled: advEnabled,
    custom_A_pre_exponential: advEnabled && formData.get("custom_A_pre_exponential") ? parseFloat(formData.get("custom_A_pre_exponential")) : null,
    custom_Ea_J_per_mol: advEnabled && formData.get("custom_Ea_J_per_mol") ? parseFloat(formData.get("custom_Ea_J_per_mol")) : null,
    custom_delta_H_J_per_g: advEnabled && formData.get("custom_delta_H_J_per_g") ? parseFloat(formData.get("custom_delta_H_J_per_g")) : null,
    custom_reaction_order_n: advEnabled && formData.get("custom_reaction_order_n") ? parseFloat(formData.get("custom_reaction_order_n")) : 1.0,
    custom_active_mass_ratio: advEnabled && formData.get("custom_active_mass_ratio") ? parseFloat(formData.get("custom_active_mass_ratio")) : null,
    h_vent_W_per_m2_K: advEnabled && formData.get("h_vent_W_per_m2_K") ? parseFloat(formData.get("h_vent_W_per_m2_K")) : 100.0,
    T_vent_gas_C: advEnabled && formData.get("T_vent_gas_C") ? parseFloat(formData.get("T_vent_gas_C")) : null,
    surface_emissivity: advEnabled && formData.get("surface_emissivity") ? parseFloat(formData.get("surface_emissivity")) : 0.85
  };
}

async function runSimulation() {
  const btnTop = document.getElementById("btnTopRunSim");
  const btnSide = document.getElementById("btnSideRunSim");

  btnTop.disabled = true;
  btnSide.disabled = true;
  btnTop.innerHTML = '<span class="btn-icon">⏳</span> Çözülüyor...';
  btnSide.innerHTML = '<span class="btn-icon">⏳</span> LSODA Entegre Ediliyor...';

  const payload = buildSimulationPayload();

  try {
    const res = await fetch("/api/simulations/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Simülasyon çözülemedi.");
    }

    const runRes = await res.json();
    const jobId = runRes.job_id;

    // Tam sonuçları getir
    const fullRes = await fetch(`/api/simulations/${jobId}/results`);
    state.simulationData = await fullRes.json();

    renderSimulationResults(state.simulationData);
    switchTreePanel("results");
  } catch (err) {
    alert(`Simülasyon Hatası: ${err.message}`);
    console.error(err);
  } finally {
    btnTop.disabled = false;
    btnSide.disabled = false;
    btnTop.innerHTML = '<span class="btn-icon">⚡</span> Simülasyonu Başlat';
    btnSide.innerHTML = '<span class="btn-icon">⚡</span> Simülasyonu Çalıştır';
  }
}

async function handleRunDesignStudy() {
  const btn = document.getElementById("btnRunDesignStudy");
  const statusBox = document.getElementById("studyStatusBox");
  const resultsContainer = document.getElementById("studyResultsContainer");

  btn.disabled = true;
  btn.innerHTML = '<span class="btn-icon">⏳</span> Varyasyonlar Çözülüyor...';
  statusBox.style.display = "block";
  resultsContainer.style.display = "none";

  const sweepType = document.getElementById("selectSweepType").value;
  const baseConfig = buildSimulationPayload();

  const studyPayload = {
    sweep_type: sweepType,
    base_config: baseConfig
  };

  try {
    const res = await fetch("/api/simulations/design-study", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(studyPayload)
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Tasarım çalışması çözülemedi.");
    }

    const data = await res.json();
    renderDesignStudyResults(data);
  } catch (err) {
    alert(`Tasarım Çalışması Hatası: ${err.message}`);
    console.error(err);
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<span class="btn-icon">📊</span> Tasarım Çalışmasını Başlat (Sweep)';
    statusBox.style.display = "none";
  }
}

function renderDesignStudyResults(data) {
  const container = document.getElementById("studyResultsContainer");
  const recText = document.getElementById("studyRecText");
  const tbody = document.getElementById("studyTableBody");

  const bestCase = data.cases[data.recommended_case_index];
  recText.textContent = `${bestCase.case_name} → ${data.recommended_reason}`;

  tbody.innerHTML = "";
  data.cases.forEach((c) => {
    const tr = document.createElement("tr");
    tr.className = `design-study-row ${c.is_recommended ? "recommended" : ""}`;

    const recBadge = c.is_recommended ? '<span class="rec-badge">★ ÖNERİLEN</span>' : '';
    const riskColor = c.risk_score_100 <= 25 ? '#10b981' : (c.risk_score_100 <= 60 ? '#f59e0b' : '#ef4444');

    tr.innerHTML = `
      <td style="font-weight:600;">${c.case_name} ${recBadge}</td>
      <td><span style="font-weight:700; color:${riskColor};">${c.risk_score_100}</span>/100</td>
      <td>${c.peak_module_temp_C.toFixed(0)}°C</td>
      <td>${c.affected_cells_count} / ${c.total_cells}</td>
      <td style="text-align:center;">
        <button type="button" class="btn-study-load" onclick="loadDesignCase('${c.job_id}')" title="Bu simülasyonu çalışma alanına yükle">
          🔍 İncele
        </button>
      </td>
    `;
    tbody.appendChild(tr);
  });

  container.style.display = "block";
}

window.loadDesignCase = async function(jobId) {
  try {
    const res = await fetch(`/api/simulations/${jobId}/results`);
    if (!res.ok) throw new Error("Varyasyon verisi alınamadı.");
    const data = await res.json();
    state.simulationData = data;
    renderSimulationResults(data);
    switchTreePanel("results");
  } catch (err) {
    alert(`Yükleme Hatası: ${err.message}`);
  }
}

function renderSimulationResults(data) {
  const evalData = data.evaluation;
  const simRes = data.simulation_result;

  // Sol ağaç durum rozetini hazır yap
  const resultsBadge = document.getElementById("statusResultsBadge");
  resultsBadge.textContent = "✓";
  resultsBadge.className = "tree-status status-ready";

  // 1. KPI Barını Güncelle
  document.getElementById("kpiTmax").textContent = `${evalData.peak_module_temp_C.toFixed(1)} °C`;
  document.getElementById("kpiTriggeredCells").textContent = `${evalData.affected_cells_count} / ${evalData.total_cells}`;
  document.getElementById("kpiPropagation").textContent = `${evalData.propagation_ratio_percent}%`;
  document.getElementById("kpiTriggerTime").textContent = evalData.time_to_first_propagation_s != null ? `${evalData.time_to_first_propagation_s.toFixed(2)} s` : "Yayılmadı";
  document.getElementById("kpiRiskScore").textContent = `${evalData.risk_score_100} / 100`;

  // Lejant Tmax
  document.getElementById("legendMaxTemp").textContent = `Tmax: ${evalData.peak_module_temp_C.toFixed(0)} °C`;

  // 2. Sağ Paneldeki Sonuç Kartı
  const badge = document.getElementById("riskBadge");
  badge.className = "risk-badge";
  if (evalData.status === "NO_PROPAGATION") {
    badge.textContent = "BAŞARILI: YAYILIM ENGELLENDİ";
    badge.classList.add("safe");
  } else if (evalData.status === "LOCAL_CONTAINED") {
    badge.textContent = "KISMEN YAYILIM (KONTROL ALTINDA)";
    badge.classList.add("contained");
  } else {
    badge.textContent = "KRİTİK RİSK: ZİNCİRLEME YAYILIM";
    badge.classList.add("danger");
  }

  document.getElementById("riskScore").textContent = `Risk: ${evalData.risk_score_100} / 100`;
  document.getElementById("riskSummary").textContent = evalData.regulatory_summary;

  // Güvenilirlik uyarısı
  const confBox = document.getElementById("confidenceBox");
  if (evalData.confidence_message) {
    confBox.style.display = "block";
    confBox.textContent = evalData.confidence_message;
  } else {
    confBox.style.display = "none";
  }

  document.getElementById("valPropTime").textContent = evalData.time_to_first_propagation_s != null ? `${evalData.time_to_first_propagation_s.toFixed(2)} s` : "Yayılmadı";
  document.getElementById("valAffectedCells").textContent = `${evalData.affected_cells_count} / ${evalData.total_cells}`;
  document.getElementById("valPeakTemp").textContent = `${evalData.peak_module_temp_C.toFixed(1)} °C`;
  document.getElementById("valHash").textContent = simRes.config_hash.substring(0, 16) + "...";

  // PDF İndirme Butonları
  const pdfUrl = `/api/simulations/${data.job_id}/report`;
  const topReportBtn = document.getElementById("btnDownloadReport");
  const sideReportBtn = document.getElementById("btnSideDownloadReport");
  topReportBtn.href = pdfUrl;
  topReportBtn.style.display = "inline-flex";
  sideReportBtn.href = pdfUrl;
  sideReportBtn.style.display = "inline-flex";

  // 3. Zaman Çizelgesi (Timeline Scrubber) Hazırla
  const scrubber = document.getElementById("timeScrubber");
  scrubber.disabled = false;
  scrubber.max = simRes.time_points_s.length - 1;
  scrubber.value = 0;
  state.currentStepIndex = 0;

  // 4. Olaylar Listesini Doldur (Event Milestones)
  renderEventTicker(evalData);

  // 5. Chart.js Grafiklerini Çiz
  renderChart(simRes);

  // 6. Animasyonu Başlat
  updateStep(0);
  startTimelineAnimation();
}

/* ================= 6. ZAMAN ÇİZELGESİ VE ANİMASYON ================= */

function initTimeline() {
  const scrubber = document.getElementById("timeScrubber");
  scrubber.addEventListener("input", (e) => {
    if (!state.simulationData) return;
    stopTimelineAnimation();
    state.currentStepIndex = parseInt(e.target.value, 10);
    updateStep(state.currentStepIndex);
  });

  const playBtn = document.getElementById("btnTimelinePlay");
  playBtn.addEventListener("click", () => {
    if (!state.simulationData) return;
    if (state.isPlaying) {
      stopTimelineAnimation();
    } else {
      startTimelineAnimation();
    }
  });

  document.getElementById("btnTimelineReset").addEventListener("click", () => {
    if (!state.simulationData) return;
    stopTimelineAnimation();
    state.currentStepIndex = 0;
    updateStep(0);
  });

  // Hız butonları
  document.querySelectorAll(".speed-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".speed-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      state.playbackSpeed = parseFloat(btn.dataset.speed);
      if (state.isPlaying) {
        startTimelineAnimation(); // Hızı yenile
      }
    });
  });
}

function updateStep(stepIdx) {
  if (!state.simulationData) return;
  const simRes = state.simulationData.simulation_result;
  const timeSec = simRes.time_points_s[stepIdx];

  document.getElementById("lblCurrentTime").textContent = `${timeSec.toFixed(2)} s`;
  document.getElementById("timeScrubber").value = stepIdx;

  updateCellStyles();
  draw2DCanvas();
  updateCellInspectorUI();
}

function startTimelineAnimation() {
  stopTimelineAnimation();
  state.isPlaying = true;
  document.getElementById("btnTimelinePlay").innerHTML = "⏸";

  const maxStep = parseInt(document.getElementById("timeScrubber").max, 10);
  const baseIntervalMs = 70;
  const interval = baseIntervalMs / state.playbackSpeed;

  state.animationTimer = setInterval(() => {
    state.currentStepIndex++;
    if (state.currentStepIndex > maxStep) {
      state.currentStepIndex = 0; // Döngü
    }
    updateStep(state.currentStepIndex);
  }, interval);
}

function stopTimelineAnimation() {
  if (state.animationTimer) {
    clearInterval(state.animationTimer);
    state.animationTimer = null;
  }
  state.isPlaying = false;
  document.getElementById("btnTimelinePlay").innerHTML = "▶";
}

function renderEventTicker(evalData) {
  const ticker = document.getElementById("eventTicker");
  ticker.innerHTML = "";

  if (!evalData.propagation_sequence || evalData.propagation_sequence.length === 0) {
    ticker.innerHTML = '<span class="event-pill normal">🏁 Yalnızca tetikleyici hücre etkilendi</span>';
    return;
  }

  evalData.propagation_sequence.forEach((ev) => {
    const pill = document.createElement("span");
    pill.className = `event-pill ${ev.is_trigger ? "trigger" : "runaway"}`;
    pill.innerHTML = `${ev.is_trigger ? "🔥 Tetikleyici" : "⚡ #" + ev.order} ${ev.name} (t=${ev.runaway_time_s.toFixed(2)}s, ${Math.round(ev.max_temperature_C)}°C)`;
    ticker.appendChild(pill);
  });
}

/* ================= 7. CHART.JS SICAKLIK EĞRİLERİ ================= */

function renderChart(simRes) {
  const ctx = document.getElementById("tempChart").getContext("2d");
  if (state.tempChart) state.tempChart.destroy();

  const timePts = simRes.time_points_s;
  const triggerId = state.simulationData.request_config.trigger_cell_id;
  const datasets = [];

  // Eşik çizgileri
  const onsetTemp = 155;
  const triggerTemp = 210;
  datasets.push({
    label: `T_onset (${onsetTemp}°C)`,
    data: new Array(timePts.length).fill(onsetTemp),
    borderColor: "#f59e0b",
    borderWidth: 1.5,
    borderDash: [6, 4],
    pointRadius: 0,
    fill: false
  });
  datasets.push({
    label: `T_trigger (${triggerTemp}°C)`,
    data: new Array(timePts.length).fill(triggerTemp),
    borderColor: "#ef4444",
    borderWidth: 1.5,
    borderDash: [4, 4],
    pointRadius: 0,
    fill: false
  });

  // Her hücre için sıcaklık eğrisi
  Object.keys(simRes.temperature_history_C).forEach(idStr => {
    const id = parseInt(idStr, 10);
    const isTrigger = id === triggerId;
    const color = isTrigger ? "#ef4444" : `hsl(${(id * 47 + 200) % 360}, 75%, 60%)`;

    datasets.push({
      label: isTrigger ? `Hücre #${id} (Tetikleyici)` : `Hücre #${id}`,
      data: simRes.temperature_history_C[id],
      borderColor: color,
      borderWidth: isTrigger ? 2.5 : 1.2,
      pointRadius: 0,
      fill: false
    });
  });

  state.tempChart = new Chart(ctx, {
    type: "line",
    data: { labels: timePts, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 0 },
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: {
          display: true,
          position: "top",
          labels: { color: "#cbd5e1", boxWidth: 12, font: { size: 10 } }
        },
        tooltip: {
          callbacks: {
            label: (c) => `${c.dataset.label}: ${c.parsed.y.toFixed(1)} °C`
          }
        }
      },
      scales: {
        x: {
          title: { display: true, text: "Zaman (saniye)", color: "#8391a2" },
          ticks: { color: "#8391a2", maxTicksLimit: 12 },
          grid: { color: "#242e3b" }
        },
        y: {
          title: { display: true, text: "Sıcaklık (°C)", color: "#8391a2" },
          ticks: { color: "#8391a2" },
          grid: { color: "#242e3b" }
        }
      }
    }
  });
}

/* ================= 8. MODALLAR VE KÜTÜPHANE YÖNETİCİSİ ================= */

function initModals() {
  // Chart Modal
  const chartModal = document.getElementById("chartModal");
  const openChartBtns = [document.getElementById("btnOpenChartsModal"), document.getElementById("btnSideOpenCharts")];
  const closeChartBtn = document.getElementById("closeChartModal");

  openChartBtns.forEach(btn => {
    if (btn) btn.addEventListener("click", () => {
      chartModal.style.display = "flex";
      if (state.simulationData) renderChart(state.simulationData.simulation_result);
    });
  });
  if (closeChartBtn) closeChartBtn.addEventListener("click", () => chartModal.style.display = "none");

  // Library Manager Modal
  const libModal = document.getElementById("libManagerModal");
  const openLibBtn = document.getElementById("btnOpenLibManager");
  const closeLibBtn = document.getElementById("closeLibManagerModal");
  const closeLibBottom = document.getElementById("btnCloseLibManagerBottom");

  if (openLibBtn) openLibBtn.addEventListener("click", () => {
    libModal.style.display = "flex";
    renderLibManager();
  });
  [closeLibBtn, closeLibBottom].forEach(b => {
    if (b) b.addEventListener("click", () => libModal.style.display = "none");
  });

  // Kütüphane sekmeleri
  const tabChems = document.getElementById("tabBtnChems");
  const tabMats = document.getElementById("tabBtnMats");
  const tabFormats = document.getElementById("tabBtnFormats");
  const cChems = document.getElementById("tabContentChems");
  const cMats = document.getElementById("tabContentMats");
  const cFormats = document.getElementById("tabContentFormats");

  function switchLibTab(btn, content) {
    [tabChems, tabMats, tabFormats].forEach(b => b.classList.remove("active"));
    [cChems, cMats, cFormats].forEach(c => c.style.display = "none");
    btn.classList.add("active");
    content.style.display = "block";
  }

  tabChems.addEventListener("click", () => switchLibTab(tabChems, cChems));
  tabMats.addEventListener("click", () => switchLibTab(tabMats, cMats));
  tabFormats.addEventListener("click", () => switchLibTab(tabFormats, cFormats));

  // Alt Modallar (Özel Kimya, Format, Malzeme)
  const chemModal = document.getElementById("customChemModal");
  const fmtModal = document.getElementById("customFormatModal");
  const matModal = document.getElementById("customMatModal");

  // Açma butonları (Hem ana sayfadan hem de kütüphane modalından)
  [document.getElementById("btnAddCustomChem"), document.getElementById("btnLibAddChem")].forEach(b => {
    if (b) b.addEventListener("click", () => chemModal.style.display = "flex");
  });
  [document.getElementById("btnAddCustomFormat"), document.getElementById("btnLibAddFormat")].forEach(b => {
    if (b) b.addEventListener("click", () => fmtModal.style.display = "flex");
  });
  [document.getElementById("btnAddCustomMat"), document.getElementById("btnLibAddMat")].forEach(b => {
    if (b) b.addEventListener("click", () => matModal.style.display = "flex");
  });

  // Kapatma butonları
  document.getElementById("closeCustomChemModal").addEventListener("click", () => chemModal.style.display = "none");
  document.getElementById("closeCustomFormatModal").addEventListener("click", () => fmtModal.style.display = "none");
  document.getElementById("closeCustomMatModal").addEventListener("click", () => matModal.style.display = "none");

  // Özel Kimya Form Gönderimi
  document.getElementById("formCustomChem").addEventListener("submit", async (e) => {
    e.preventDefault();
    const payload = {
      name: document.getElementById("cc_name").value,
      A_pre_exponential_per_s: parseFloat(document.getElementById("cc_A").value),
      Ea_J_per_mol: parseFloat(document.getElementById("cc_Ea").value),
      delta_H_J_per_g: parseFloat(document.getElementById("cc_dH").value),
      active_mass_ratio: parseFloat(document.getElementById("cc_ratio").value),
      T_onset_C: parseFloat(document.getElementById("cc_Tonset").value),
      T_trigger_C: parseFloat(document.getElementById("cc_Ttrigger").value),
      source_references: ["Kullanıcı Tanımlı (User Defined)"]
    };

    try {
      const res = await fetch("/api/chemistry/custom", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        chemModal.style.display = "none";
        await loadLibraries();
        const json = await res.json();
        document.getElementById("selectChemistry").value = json.chemistry_id;
        updateChemistryDetails();
        renderLibManager();
      }
    } catch (err) { console.error(err); }
  });

  // Özel Format Form Gönderimi
  document.getElementById("formCustomFormat").addEventListener("submit", async (e) => {
    e.preventDefault();
    const payload = {
      format_name: document.getElementById("cf_name").value,
      radius_mm: parseFloat(document.getElementById("cf_r").value),
      height_mm: parseFloat(document.getElementById("cf_h").value),
      mass_kg: parseFloat(document.getElementById("cf_mass").value),
      casing_thickness_mm: parseFloat(document.getElementById("cf_t").value)
    };

    try {
      const res = await fetch("/api/formats/custom", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        fmtModal.style.display = "none";
        await loadLibraries();
        const json = await res.json();
        document.getElementById("selectFormat").value = json.format_id;
        updatePackLayoutFromInputs();
        renderLibManager();
      }
    } catch (err) { console.error(err); }
  });

  // Özel Malzeme Form Gönderimi
  document.getElementById("formCustomMat").addEventListener("submit", async (e) => {
    e.preventDefault();
    const payload = {
      name: document.getElementById("cm_name").value,
      k_thermal_W_per_m_K: parseFloat(document.getElementById("cm_k").value),
      density_kg_per_m3: parseFloat(document.getElementById("cm_rho").value),
      cp_J_per_kg_K: parseFloat(document.getElementById("cm_cp").value)
    };

    try {
      const res = await fetch("/api/materials/custom", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        matModal.style.display = "none";
        await loadLibraries();
        const json = await res.json();
        document.getElementById("selectSeparator").value = json.material_id;
        renderLibManager();
      }
    } catch (err) { console.error(err); }
  });
}

async function renderLibManager() {
  try {
    const res = await fetch("/api/library/summary");
    if (!res.ok) return;
    const data = await res.json();

    // 1. Kimyalar
    const chemsList = document.getElementById("libChemsList");
    chemsList.innerHTML = "";
    data.chemistries.forEach(c => {
      const isCustom = c.source_type === "user_defined";
      const card = document.createElement("div");
      card.className = `lib-item-card ${isCustom ? "custom" : ""}`;
      card.innerHTML = `
        <div>
          <div style="font-weight:600; color:#f8fafc; font-size:12px;">
            ${c.name} ${isCustom ? '<span style="background:rgba(16, 185, 129, 0.2); color:#34d399; font-size:9px; padding:2px 6px; border-radius:3px; margin-left:6px;">Özel</span>' : '<span style="background:rgba(255,255,255,0.06); color:#94a3b8; font-size:9px; padding:2px 6px; border-radius:3px; margin-left:6px;">Literatür</span>'}
          </div>
          <div style="font-size:10px; color:#8391a2; margin-top:3px;">
            Onset: <strong>${c.T_onset_C}°C</strong> | Trigger: <strong>${c.T_trigger_C}°C</strong> | ΔH: <strong>${c.delta_H_J_per_g} J/g</strong> | Ea: <strong>${c.Ea_kJ_per_mol} kJ/mol</strong>
          </div>
        </div>
        ${isCustom ? `<button class="btn ghost-btn micro-btn" style="color:#ef4444;" onclick="deleteLibItem('chemistry', '${c.chemistry_id}')">Sil</button>` : ''}
      `;
      chemsList.appendChild(card);
    });

    // 2. Malzemeler
    const matsList = document.getElementById("libMatsList");
    matsList.innerHTML = "";
    Object.keys(data.materials).forEach(key => {
      const m = data.materials[key];
      const isCustom = m.source_type === "user_defined";
      const card = document.createElement("div");
      card.className = `lib-item-card ${isCustom ? "custom" : ""}`;
      card.innerHTML = `
        <div>
          <div style="font-weight:600; color:#f8fafc; font-size:12px;">
            ${m.name || key} ${isCustom ? '<span style="background:rgba(16, 185, 129, 0.2); color:#34d399; font-size:9px; padding:2px 6px; border-radius:3px; margin-left:6px;">Özel</span>' : '<span style="background:rgba(255,255,255,0.06); color:#94a3b8; font-size:9px; padding:2px 6px; border-radius:3px; margin-left:6px;">Yerleşik</span>'}
          </div>
          <div style="font-size:10px; color:#8391a2; margin-top:3px;">
            İletkenlik (k): <strong>${m.k_thermal_W_per_m_K} W/mK</strong> | Yoğunluk: <strong>${m.density_kg_per_m3} kg/m³</strong> | Cp: <strong>${m.cp_J_per_kg_K} J/kgK</strong>
          </div>
        </div>
        ${isCustom ? `<button class="btn ghost-btn micro-btn" style="color:#ef4444;" onclick="deleteLibItem('material', '${key}')">Sil</button>` : ''}
      `;
      matsList.appendChild(card);
    });

    // 3. Formatlar
    const formatsList = document.getElementById("libFormatsList");
    formatsList.innerHTML = "";
    Object.keys(data.formats).forEach(key => {
      const f = data.formats[key];
      const isCustom = f.source_type === "user_defined";
      const card = document.createElement("div");
      card.className = `lib-item-card ${isCustom ? "custom" : ""}`;
      const dims = f.type === "prismatic"
        ? `En: ${Math.round(f.width * 1000)}mm, Boy: ${Math.round(f.height * 1000)}mm`
        : `Çap: ${Math.round(f.radius * 2000)}mm, Yükseklik: ${Math.round(f.height * 1000)}mm`;
      card.innerHTML = `
        <div>
          <div style="font-weight:600; color:#f8fafc; font-size:12px;">
            ${key} ${isCustom ? '<span style="background:rgba(16, 185, 129, 0.2); color:#34d399; font-size:9px; padding:2px 6px; border-radius:3px; margin-left:6px;">Özel</span>' : '<span style="background:rgba(255,255,255,0.06); color:#94a3b8; font-size:9px; padding:2px 6px; border-radius:3px; margin-left:6px;">Standart</span>'}
          </div>
          <div style="font-size:10px; color:#8391a2; margin-top:3px;">
            ${dims} | Kütle: <strong>${f.mass} kg</strong>
          </div>
        </div>
        ${isCustom ? `<button class="btn ghost-btn micro-btn" style="color:#ef4444;" onclick="deleteLibItem('format', '${key}')">Sil</button>` : ''}
      `;
      formatsList.appendChild(card);
    });
  } catch (err) {
    console.error("Kütüphane listesi yüklenemedi:", err);
  }
}

window.deleteLibItem = async function(type, id) {
  if (!confirm(`'${id}' öğesini silmek istediğinize emin misiniz?`)) return;
  const endpoint = type === "chemistry" ? `/api/chemistry/custom/${id}` : (type === "material" ? `/api/materials/custom/${id}` : `/api/formats/custom/${id}`);
  try {
    const res = await fetch(endpoint, { method: "DELETE" });
    if (res.ok) {
      await loadLibraries();
      await renderLibManager();
      updateChemistryDetails();
      updatePackLayoutFromInputs();
    }
  } catch (err) {
    console.error(err);
  }
};
