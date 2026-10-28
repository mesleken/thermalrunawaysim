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
  validationResult: null,
  monteCarloResult: null,
  currentStepIndex: 0,
  isPlaying: false,
  playbackSpeed: 1.0,
  animationTimer: null,
  tempChart: null,
  drawerChart: null,
  drawerActiveTab: "temp",
  drawerExpanded: false,
  compareChart: null,
  acFitChart: null,
  tornadoChart: null,
  lastCalibratedChem: null,
  lastCellCoords: {},
  loadedChemistries: {},
  loadedMaterials: {},
  loadedFormats: {},
  loadedPresets: {}
};

function getFormatGeometryType(formatKey) {
  if (!formatKey) return "cylindrical";
  const fmtObj = state.loadedFormats[formatKey];
  if (fmtObj && fmtObj.type) {
    if (fmtObj.type === "pouch") return "pouch";
    if (fmtObj.type === "prismatic") return "prismatic";
    return "cylindrical";
  }
  const low = String(formatKey).toLowerCase();
  if (low.includes("pouch")) return "pouch";
  if (low.includes("prismatic") || low.includes("blade")) return "prismatic";
  return "cylindrical";
}

document.addEventListener("DOMContentLoaded", () => {
  initTreeNavigation();
  initFormBindings();
  initViewerControls();
  initTimeline();
  initModals();
  initAnalyticsDrawer();
  initPresets();
  initProjectManager();
  initCompareManager();
  initAutoCalibrator();
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
        let desc = "";
        if (f.type === "prismatic" || f.type === "pouch") {
          const wMm = Math.round((f.width || 0.148) * 1000);
          const tMm = Math.round((f.thickness || f.depth || 0.015) * 1000);
          const hMm = Math.round((f.height || 0.100) * 1000);
          const typeTag = f.type === "pouch" ? "Kese" : "Prizmatik";
          desc = `${typeTag}: ${wMm}x${tMm}x${hMm} mm`;
        } else {
          desc = `Silindirik: ${Math.round((f.radius || 0.009) * 2000)}x${Math.round((f.height || 0.065) * 1000)} mm`;
        }
        fmtSelect.innerHTML += `<option value="${key}">${key}${isCustom} (${desc})</option>`;
      });

      if (curFmt && fmtData[curFmt]) fmtSelect.value = curFmt;
      else if (curFmt === "prismatic" && fmtData["Prismatic_50Ah"]) fmtSelect.value = "Prismatic_50Ah";
      else if (curFmt === "pouch" && fmtData["Pouch_60Ah"]) fmtSelect.value = "Pouch_60Ah";
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
    "panelExcitation", "panelSimulation", "panelDesignStudy", "panelValidation", "panelResults", "panelCellInspector"
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
    case "validation":
      titleEl.textContent = "KANIT & VALİDASYON MOTORU";
      badgeEl.textContent = "EVIDENCE";
      document.getElementById("panelValidation").style.display = "block";
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

  // SOC Seviyesi slider'ı
  const socSlider = document.getElementById("inputSocPercent");
  const socLabel = document.getElementById("lblSocPercent");
  if (socSlider && socLabel) {
    socSlider.addEventListener("input", (e) => {
      socLabel.textContent = `${e.target.value}%`;
    });
  }

  // Tetikleme tipi toggle (5 Abuse Modu: pulse, external heater, nail ISC, oven ramp, instant onset)
  const selectTrigger = document.getElementById("selectTriggerMethod");
  const groupThermalPulse = document.getElementById("groupThermalPulse");
  const groupInstantOnset = document.getElementById("groupInstantOnset");
  const groupISC = document.getElementById("groupISC");
  const groupOven = document.getElementById("groupOven");

  function updateTriggerDisplay(val) {
    if (groupThermalPulse) groupThermalPulse.style.display = (val === "thermal_pulse" || val === "external_heater") ? "grid" : "none";
    if (groupInstantOnset) groupInstantOnset.style.display = (val === "instant_onset") ? "block" : "none";
    if (groupISC) groupISC.style.display = (val === "nail_penetration_isc") ? "block" : "none";
    if (groupOven) groupOven.style.display = (val === "oven_ramp") ? "grid" : "none";
  }

  if (selectTrigger) {
    selectTrigger.addEventListener("change", (e) => updateTriggerDisplay(e.target.value));
    updateTriggerDisplay(selectTrigger.value);
  }

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

  // Kinetik model değişimi (Tek-Adım vs 4-Kademeli Çoklu Reaksiyon Tablosu)
  const selectKineticsModel = document.getElementById("selectKineticsModel");
  const singleStepFields = document.getElementById("singleStepKineticsFields");
  const multiRxnContainer = document.getElementById("multiReactionTableContainer");
  function syncKineticsModelUI() {
    const isMulti = selectKineticsModel?.value === "multi_reaction";
    if (singleStepFields) singleStepFields.style.display = isMulti ? "none" : "block";
    if (multiRxnContainer) multiRxnContainer.style.display = isMulti ? "block" : "none";
    if (isMulti) renderSubReactionTable();
  }
  if (selectKineticsModel) {
    selectKineticsModel.addEventListener("change", syncKineticsModelUI);
    syncKineticsModelUI();
  }
  const btnResetSubRxns = document.getElementById("btnResetSubReactions");
  if (btnResetSubRxns) {
    btnResetSubRxns.addEventListener("click", () => renderSubReactionTable(true));
  }

  // Tasarım Çalışması (Design Study) mod ve tür değişimi
  const selectStudyMode = document.getElementById("selectStudyMode");
  const study1DControls = document.getElementById("study1DControls");
  const study2DControls = document.getElementById("study2DControls");
  const studyTornadoControls = document.getElementById("studyTornadoControls");
  if (selectStudyMode) {
    selectStudyMode.addEventListener("change", (e) => {
      const m = e.target.value;
      if (study1DControls) study1DControls.style.display = (m === "1d_pareto") ? "block" : "none";
      if (study2DControls) study2DControls.style.display = (m === "2d_grid") ? "block" : "none";
      if (studyTornadoControls) studyTornadoControls.style.display = (m === "tornado_oat") ? "block" : "none";
    });
  }

  const selectSweep = document.getElementById("selectSweepType");
  if (selectSweep) {
    selectSweep.addEventListener("change", updateSweepPills);
  }

  // Aşama 3: Kütle vs Güvenlik Ağırlık Slider'ları
  const sliderWSafety = document.getElementById("inputSweepWSafety");
  const sliderWMass = document.getElementById("inputSweepWMass");
  const lblWSafety = document.getElementById("lblWSafety");
  const lblWMass = document.getElementById("lblWMass");
  if (sliderWSafety && sliderWMass) {
    sliderWSafety.addEventListener("input", (e) => {
      const sVal = parseInt(e.target.value, 10);
      const mVal = 100 - sVal;
      sliderWMass.value = mVal;
      lblWSafety.textContent = `%${sVal}`;
      lblWMass.textContent = `%${mVal}`;
    });
    sliderWMass.addEventListener("input", (e) => {
      const mVal = parseInt(e.target.value, 10);
      const sVal = 100 - mVal;
      sliderWSafety.value = sVal;
      lblWSafety.textContent = `%${sVal}`;
      lblWMass.textContent = `%${mVal}`;
    });
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

  // Validasyon ve Kanıt Motoru (Aşama 2)
  const fileValCsv = document.getElementById("inputValidationCsvFile");
  if (fileValCsv) {
    fileValCsv.addEventListener("change", (e) => {
      const file = e.target.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = (evt) => {
        document.getElementById("textareaValidationCsv").value = evt.target.result;
      };
      reader.readAsText(file);
    });
  }

  const btnValCompare = document.getElementById("btnRunValidationCompare");
  if (btnValCompare) {
    btnValCompare.addEventListener("click", handleRunValidationCompare);
  }

  const btnMonteCarlo = document.getElementById("btnRunMonteCarlo");
  if (btnMonteCarlo) {
    btnMonteCarlo.addEventListener("click", handleRunMonteCarlo);
  }

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

  const onset = Number(chem.T_onset_C ?? (chem.T_onset_K - 273.15));
  const trigger = Number(chem.T_trigger_C ?? (chem.T_trigger_K - 273.15));
  const ea = chem.Ea_kJ_per_mol || (chem.Ea_J_per_mol / 1000).toFixed(1);

  document.getElementById("chemValOnset").textContent = `${Math.round(onset)} °C`;
  document.getElementById("chemValTrigger").textContent = `${Math.round(trigger)} °C`;
  document.getElementById("chemValDeltaH").textContent = `${chem.delta_H_J_per_g} J/g`;
  document.getElementById("chemValEa").textContent = `${ea} kJ/mol`;

  // Sıcaklık lejantındaki dinamik Onset ve TR etiketlerini güncelle
  const tickOnset = document.getElementById("legendTickOnset");
  const tickTr = document.getElementById("legendTickTr");
  if (tickOnset) tickOnset.textContent = `${Math.round(onset)}°C (Onset)`;
  if (tickTr) tickTr.textContent = `${Math.round(trigger)}°C (TR)`;

  // Proje başlığı etiketini güncelle
  const fmt = document.getElementById("selectFormat").value;
  document.getElementById("projectTitle").textContent = `${fmt} / ${chem.name || chemId} Modülü`;

  // Çoklu reaksiyon tablosunu seçili kimyaya göre tazele
  renderSubReactionTable(true);
  updateCellStyles();
  draw2DCanvas();
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
    rotX = 28;
    rotZ = -8;
    scale3d = 1.0;
    const stage = document.getElementById("pack3dStage");
    stage.style.transform = "scale(1.0) rotateX(28deg) rotateZ(-8deg)";
  });

  document.getElementById("btnToggleLabels").addEventListener("click", () => {
    state.showLabels = !state.showLabels;
    updateCellStyles();
    draw2DCanvas();
  });

  // 3D Etkileşimli Drag-to-Orbit ve Yakınlaştırma (Orbit Controls)
  let isDragging3D = false;
  let prevMouseX = 0, prevMouseY = 0;
  let rotX = 28, rotZ = -8, scale3d = 1.0;
  const stage = document.getElementById("pack3dStage");

  viewer3D.addEventListener("mousedown", (e) => {
    if (state.viewMode !== "3d") return;
    isDragging3D = true;
    prevMouseX = e.clientX;
    prevMouseY = e.clientY;
    viewer3D.style.cursor = "grabbing";
  });

  window.addEventListener("mousemove", (e) => {
    if (!isDragging3D || state.viewMode !== "3d") return;
    const dx = e.clientX - prevMouseX;
    const dy = e.clientY - prevMouseY;
    prevMouseX = e.clientX;
    prevMouseY = e.clientY;
    rotX = Math.max(0, Math.min(85, rotX - dy * 0.4));
    rotZ = (rotZ + dx * 0.4) % 360;
    stage.style.transform = `scale(${scale3d}) rotateX(${rotX}deg) rotateZ(${rotZ}deg)`;
  });

  window.addEventListener("mouseup", () => {
    isDragging3D = false;
    viewer3D.style.cursor = "default";
  });

  viewer3D.addEventListener("wheel", (e) => {
    if (state.viewMode !== "3d") return;
    e.preventDefault();
    scale3d = Math.max(0.5, Math.min(2.5, scale3d - e.deltaY * 0.0012));
    stage.style.transform = `scale(${scale3d}) rotateX(${rotX}deg) rotateZ(${rotZ}deg)`;
  }, { passive: false });

  // 2D Kanvas Tıklama, Sağ-Tık Tetikleyici Atama ve Üzerine Gelince (Hover) Bilgi Kutusu
  const canvas = document.getElementById("packCanvas");
  const hoverTooltip = document.getElementById("canvasHoverTooltip");
  if (canvas) {
    function findHoveredCell(e) {
      if (state.viewMode === "3d" || !state.lastCellCoords) return null;
      const rect = canvas.getBoundingClientRect();
      const scaleX = canvas.width / rect.width;
      const scaleY = canvas.height / rect.height;
      const mouseX = (e.clientX - rect.left) * scaleX;
      const mouseY = (e.clientY - rect.top) * scaleY;

      let closestId = null;
      let minDist = Infinity;
      Object.keys(state.lastCellCoords).forEach(idStr => {
        const id = parseInt(idStr, 10);
        const pt = state.lastCellCoords[id];
        const d = Math.hypot(mouseX - pt.x, mouseY - pt.y);
        if (d < minDist) {
          minDist = d;
          closestId = id;
        }
      });
      return (closestId !== null && minDist <= 38) ? closestId : null;
    }

    canvas.addEventListener("click", (e) => {
      const cid = findHoveredCell(e);
      if (cid !== null) {
        selectCell(cid);
      }
    });

    canvas.addEventListener("contextmenu", (e) => {
      const cid = findHoveredCell(e);
      if (cid !== null) {
        e.preventDefault();
        document.getElementById("inputTriggerCell").value = cid;
        selectCell(cid);
        updateCellStyles();
        draw2DCanvas();
      }
    });

    canvas.addEventListener("mousemove", (e) => {
      if (!hoverTooltip) return;
      const cid = findHoveredCell(e);
      if (cid === null) {
        hoverTooltip.style.display = "none";
        canvas.style.cursor = "default";
        return;
      }
      canvas.style.cursor = "pointer";
      const viewerRect = document.getElementById("battery2DViewer").getBoundingClientRect();
      const { tOnset, tTrigger } = getChemistryThresholds();
      let temp = 25.0, coreTemp = 25.0, alpha = 0.0;
      if (state.simulationData) {
        const simRes = state.simulationData.simulation_result;
        const step = state.currentStepIndex;
        temp = simRes.temperature_history_C[cid] ? simRes.temperature_history_C[cid][step] : 25.0;
        coreTemp = (simRes.core_temperature_history_C && simRes.core_temperature_history_C[cid])
          ? simRes.core_temperature_history_C[cid][step] : temp;
        alpha = simRes.alpha_history[cid] ? simRes.alpha_history[cid][step] : 0.0;
      }
      let statusLabel = "Normal";
      let statusCol = "#34d399";
      if (alpha >= 0.99) { statusLabel = "Tükendi"; statusCol = "#94a3b8"; }
      else if (temp >= tTrigger) { statusLabel = "TERMAL KAÇAK"; statusCol = "#f87171"; }
      else if (temp >= tOnset) { statusLabel = "Onset (Ekzotermik)"; statusCol = "#fb923c"; }
      else if (temp >= 60) { statusLabel = "Isınma"; statusCol = "#facc15"; }

      const isTrig = cid === parseInt(document.getElementById("inputTriggerCell").value, 10);
      hoverTooltip.innerHTML = `
        <div style="font-weight:800; color:#38bdf8; border-bottom:1px solid #1e293b; padding-bottom:3px; margin-bottom:4px;">
          Hücre #${cid} ${isTrig ? '<span style="color:#f43f5e;">(⚡ Tetik)</span>' : ''}
        </div>
        <div>Kovan (T<sub>shell</sub>): <strong>${temp.toFixed(1)} °C</strong></div>
        <div>Çekirdek (T<sub>core</sub>): <strong>${coreTemp.toFixed(1)} °C</strong></div>
        <div>Dönüşüm (α): <strong>${alpha.toFixed(3)}</strong></div>
        <div>Durum: <strong style="color:${statusCol};">${statusLabel}</strong></div>
        <div style="font-size:8.5px; color:#64748b; margin-top:3px;">Sol Tık: İncele | Sağ Tık: Tetikleyici Yap</div>
      `;
      hoverTooltip.style.left = `${Math.min(viewerRect.width - 175, Math.max(8, e.clientX - viewerRect.left + 14))}px`;
      hoverTooltip.style.top = `${Math.min(viewerRect.height - 125, Math.max(8, e.clientY - viewerRect.top + 14))}px`;
      hoverTooltip.style.display = "block";
    });

    canvas.addEventListener("mouseleave", () => {
      if (hoverTooltip) hoverTooltip.style.display = "none";
    });
  }
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

  // Gerçek kütüphane boyutlarıyla modül en x boy hesabı
  const geomType = getFormatGeometryType(format);
  const fmtInfo = state.loadedFormats[format];
  let cellSpanX = 18, cellSpanY = 18;
  if (fmtInfo) {
    if (geomType === "prismatic" || geomType === "pouch") {
      cellSpanX = (fmtInfo.width || 0.148) * 1000;
      cellSpanY = (fmtInfo.thickness || fmtInfo.depth || 0.015) * 1000;
    } else {
      const d = (fmtInfo.radius || 0.009) * 2000;
      cellSpanX = d;
      cellSpanY = d;
    }
  } else if (format === "21700") {
    cellSpanX = cellSpanY = 21;
  } else if (format === "4680") {
    cellSpanX = cellSpanY = 46;
  } else if (geomType === "prismatic") {
    cellSpanX = 148; cellSpanY = 27;
  } else if (geomType === "pouch") {
    cellSpanX = 220; cellSpanY = 11;
  }

  const packW = Math.round(cols * cellSpanX + Math.max(0, cols - 1) * spacingX);
  const packH = Math.round(rows * cellSpanY + Math.max(0, rows - 1) * spacingY);
  document.getElementById("calcPackDims").textContent = `~${packW} x ${packH} mm`;

  // Tetikleyici sınır kontrolü
  const triggerInput = document.getElementById("inputTriggerCell");
  if (parseInt(triggerInput.value, 10) >= totalCells) {
    triggerInput.value = 0;
  }
  triggerInput.max = Math.max(0, totalCells - 1);

  // 3D Hücre Sahnesi Oluştur
  render3DStage(rows, cols, staggered, format);
  draw2DCanvas();
}

function render3DStage(rows, cols, staggered, format) {
  const stage = document.getElementById("pack3dStage");
  stage.innerHTML = "";
  const geomType = getFormatGeometryType(format);
  const colPitchPx = (geomType === "prismatic" || geomType === "pouch") ? 64 : 54;
  stage.style.gridTemplateColumns = `repeat(${cols}, ${colPitchPx}px)`;

  const totalCells = rows * cols;
  const triggerCellId = parseInt(document.getElementById("inputTriggerCell").value, 10);

  for (let id = 0; id < totalCells; id++) {
    const row = Math.floor(id / cols);

    const cell = document.createElement("div");
    cell.className = "cell-3d";
    if (geomType === "prismatic") cell.classList.add("prismatic");
    else if (geomType === "pouch") cell.classList.add("pouch");
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

  // Alt analitik çekmecesi açıksa grafiği seçili hücreye göre tazele
  if (state.simulationData && ["kinetics", "rate", "temp", "flux"].includes(state.drawerActiveTab)) {
    renderDrawerChart(state.drawerActiveTab);
  }
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
      if (summary.max_core_temperature_C && summary.max_core_temperature_C !== summary.max_temperature_C) {
        document.getElementById("inspectCellMaxTemp").textContent = `${summary.max_temperature_C.toFixed(1)} °C (Core: ${summary.max_core_temperature_C.toFixed(1)} °C)`;
      } else {
        document.getElementById("inspectCellMaxTemp").textContent = `${summary.max_temperature_C.toFixed(1)} °C`;
      }
      const lagTxt = summary.thermal_lag_s > 0 ? ` (Gecikme: ${summary.thermal_lag_s.toFixed(2)}s)` : '';
      document.getElementById("inspectCellRunawayTime").textContent = (summary.runaway_time_s != null ? `${summary.runaway_time_s.toFixed(2)} s` : "Yayılmadı") + lagTxt;
      document.getElementById("inspectCellCoords").textContent = `X: ${summary.pos_x_mm.toFixed(1)} mm, Y: ${summary.pos_y_mm.toFixed(1)} mm`;
      document.getElementById("inspectCellMass").textContent = `${(summary.mass_kg * 1000).toFixed(1)} g`;
    }

    // Durum etiketi (Seçili kimyanın dinamik T_onset ve T_trigger eşiklerine göre)
    const { tOnset, tTrigger } = getChemistryThresholds();
    const statusTag = document.getElementById("inspectCellStatus");
    if (alpha >= 0.99) {
      statusTag.textContent = "TÜKENDİ (BURNED)";
      statusTag.style.color = "#94a3b8";
    } else if (temp >= tTrigger) {
      statusTag.textContent = "TERMAL KAÇAK (RUNAWAY)";
      statusTag.style.color = "#ef4444";
    } else if (temp >= tOnset) {
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

function getChemistryThresholds() {
  const firstSummary = state.simulationData?.simulation_result?.cell_summaries?.[0];
  if (firstSummary && firstSummary.T_onset_C != null && firstSummary.T_trigger_C != null) {
    return {
      tOnset: Number(firstSummary.T_onset_C),
      tTrigger: Number(firstSummary.T_trigger_C)
    };
  }
  const chemId = document.getElementById("selectChemistry")?.value;
  const chem = state.loadedChemistries[chemId];
  const tOnset = Number(chem?.T_onset_C ?? (chem?.T_onset_K ? chem.T_onset_K - 273.15 : 155.0));
  const tTrigger = Number(chem?.T_trigger_C ?? (chem?.T_trigger_K ? chem.T_trigger_K - 273.15 : 210.0));
  return { tOnset, tTrigger };
}

function getTemperatureColor(tempC, alpha) {
  if (alpha >= 0.99) return "#475569"; // Burned out
  const { tOnset, tTrigger } = getChemistryThresholds();
  if (tempC >= tTrigger) return "#dc2626";  // Runaway
  if (tempC >= tOnset) return "#f97316";    // Onset
  if (tempC >= 60) return "#eab308";       // Warming
  return "#2563eb";                        // Normal cool
}

function updateCellStyles() {
  const triggerCellId = parseInt(document.getElementById("inputTriggerCell").value, 10);
  const totalCells = parseInt(document.getElementById("inputRows").value, 10) * parseInt(document.getElementById("inputCols").value, 10);
  const { tOnset, tTrigger } = getChemistryThresholds();

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

      cellEl.classList.remove("warming", "onset", "runaway", "burned");

      if (alpha >= 0.99) cellEl.classList.add("burned");
      else if (temp >= tTrigger) cellEl.classList.add("runaway");
      else if (temp >= tOnset) cellEl.classList.add("onset");
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
  const isHeatmap = (state.viewMode === "heatmap");
  ctx.fillStyle = isHeatmap ? "#050811" : "#0b0f15";
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  const rows = parseInt(document.getElementById("inputRows").value, 10) || 3;
  const cols = parseInt(document.getElementById("inputCols").value, 10) || 3;
  const staggered = document.getElementById("checkboxStaggered").checked;
  const triggerCellId = parseInt(document.getElementById("inputTriggerCell").value, 10);
  const format = document.getElementById("selectFormat").value;
  const geomType = getFormatGeometryType(format);
  const isPrismatic = (geomType === "prismatic");
  const isPouch = (geomType === "pouch");
  const sepMatId = document.getElementById("selectSeparator")?.value;
  const sepThick = parseFloat(document.getElementById("inputSepThickness")?.value || 0);
  const sepMaxTempC = sepMatId && state.loadedMaterials[sepMatId]?.max_service_temp_C
    ? Number(state.loadedMaterials[sepMatId].max_service_temp_C)
    : 850.0;

  const marginX = 80;
  const marginY = 60;
  const availableW = canvas.width - marginX * 2;
  const availableH = canvas.height - marginY * 2;

  const pitchX = availableW / Math.max(1, cols - 1 || 1);
  const pitchY = availableH / Math.max(1, rows - 1 || 1);
  const radius = Math.min(26, Math.min(pitchX, pitchY) * 0.38);

  const cellCoords = {};

  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const id = r * cols + c;
      const offsetX = (staggered && r % 2 === 1) ? pitchX * 0.5 : 0;
      const x = (cols === 1) ? (canvas.width / 2) : (marginX + c * pitchX + offsetX);
      const y = (rows === 1) ? (canvas.height / 2) : (marginY + r * pitchY);
      cellCoords[id] = { x, y, r, c };
    }
  }
  state.lastCellCoords = cellCoords;

  const getCellCurrentTemp = (cid) => {
    if (!state.simulationData) return 25.0;
    const simRes = state.simulationData.simulation_result;
    const step = state.currentStepIndex;
    return simRes.temperature_history_C[cid] ? simRes.temperature_history_C[cid][step] : 25.0;
  };

  // 1. Hücreler Arası Termal İletim ve Bariyer Şeritleri (Bozunma Uyarısı Dahil)
  if (!isHeatmap) {
    ctx.strokeStyle = "#1e293b";
    ctx.lineWidth = 2;
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const id = r * cols + c;
        if (c + 1 < cols) {
          const rightId = r * cols + (c + 1);
          ctx.beginPath();
          ctx.moveTo(cellCoords[id].x, cellCoords[id].y);
          ctx.lineTo(cellCoords[rightId].x, cellCoords[rightId].y);
          ctx.strokeStyle = "#1e293b";
          ctx.lineWidth = 2;
          ctx.stroke();

          // Dikey Separatör Bariyeri Çizimi
          if (sepMatId && sepThick > 0) {
            const midX = (cellCoords[id].x + cellCoords[rightId].x) / 2;
            const midY = (cellCoords[id].y + cellCoords[rightId].y) / 2;
            const degraded = Math.max(getCellCurrentTemp(id), getCellCurrentTemp(rightId)) > sepMaxTempC;
            if (degraded) {
              ctx.save();
              ctx.strokeStyle = "#ef4444";
              ctx.lineWidth = 3;
              ctx.setLineDash([4, 3]);
              ctx.beginPath();
              ctx.moveTo(midX, midY - radius);
              ctx.lineTo(midX, midY + radius);
              ctx.stroke();
              ctx.restore();
            } else {
              let barrierColor = "#94a3b8";
              if (sepMatId === "aerogel_insulation") barrierColor = "#f8fafc";
              else if (sepMatId === "paraffin_pcm_pad") barrierColor = "#38bdf8";
              else if (sepMatId === "ceramic_intumescent_mat") barrierColor = "#fb923c";
              ctx.fillStyle = barrierColor;
              ctx.fillRect(midX - 2.5, midY - radius, 5, radius * 2);
            }
          }
        }
        if (r + 1 < rows) {
          const bottomId = (r + 1) * cols + c;
          ctx.beginPath();
          ctx.moveTo(cellCoords[id].x, cellCoords[id].y);
          ctx.lineTo(cellCoords[bottomId].x, cellCoords[bottomId].y);
          ctx.strokeStyle = "#1e293b";
          ctx.lineWidth = 2;
          ctx.stroke();

          // Yatay Separatör Bariyeri Çizimi
          if (sepMatId && sepThick > 0) {
            const midX = (cellCoords[id].x + cellCoords[bottomId].x) / 2;
            const midY = (cellCoords[id].y + cellCoords[bottomId].y) / 2;
            const degraded = Math.max(getCellCurrentTemp(id), getCellCurrentTemp(bottomId)) > sepMaxTempC;
            if (degraded) {
              ctx.save();
              ctx.strokeStyle = "#ef4444";
              ctx.lineWidth = 3;
              ctx.setLineDash([4, 3]);
              ctx.beginPath();
              ctx.moveTo(midX - radius, midY);
              ctx.lineTo(midX + radius, midY);
              ctx.stroke();
              ctx.restore();
            } else {
              let barrierColor = "#94a3b8";
              if (sepMatId === "aerogel_insulation") barrierColor = "#f8fafc";
              else if (sepMatId === "paraffin_pcm_pad") barrierColor = "#38bdf8";
              else if (sepMatId === "ceramic_intumescent_mat") barrierColor = "#fb923c";
              ctx.fillStyle = barrierColor;
              ctx.fillRect(midX - radius, midY - 2.5, radius * 2, 5);
            }
          }
        }
      }
    }
  }

  // 2. Sürekli Isı Haritası (Continuous Gradient Heatmap Mode)
  if (isHeatmap) {
    ctx.save();
    ctx.globalCompositeOperation = "screen";
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
      const heatR = radius * 3.2;
      const grad = ctx.createRadialGradient(coord.x, coord.y, 2, coord.x, coord.y, heatR);
      const baseCol = getTemperatureColor(temp, alpha);
      grad.addColorStop(0, baseCol);
      grad.addColorStop(0.5, baseCol + "99");
      grad.addColorStop(1, "rgba(5, 8, 17, 0)");
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.arc(coord.x, coord.y, heatR, 0, 2 * Math.PI);
      ctx.fill();
    });
    ctx.restore();
  }

  // 3. Yayılım Grafiği Okları (Causal Directed DAG)
  if (state.simulationData && !isHeatmap) {
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
        ctx.setLineDash([5, 4]);
        ctx.stroke();
        ctx.setLineDash([]);
      }
    });
  }

  // 4. Hücreleri Gerçek Kesit Geometrisine Göre Çiz
  const { tTrigger } = getChemistryThresholds();
  const isCoreShell = (document.getElementById("selectNodalModel")?.value === "core_shell");

  Object.keys(cellCoords).forEach(idStr => {
    const id = parseInt(idStr, 10);
    const coord = cellCoords[id];

    let temp = 25.0;
    let coreTemp = 25.0;
    let alpha = 0.0;
    if (state.simulationData) {
      const simRes = state.simulationData.simulation_result;
      const step = state.currentStepIndex;
      temp = simRes.temperature_history_C[id] ? simRes.temperature_history_C[id][step] : 25.0;
      coreTemp = (simRes.core_temperature_history_C && simRes.core_temperature_history_C[id])
        ? simRes.core_temperature_history_C[id][step] : temp;
      alpha = simRes.alpha_history[id] ? simRes.alpha_history[id][step] : 0.0;
    }

    const fillColor = getTemperatureColor(temp, alpha);
    const coreColor = getTemperatureColor(coreTemp, alpha);

    // Runaway Alev Parlaması ve Aktif Venting Konisi (0.05 < alpha < 0.98)
    if (temp >= tTrigger && alpha < 0.98) {
      ctx.beginPath();
      ctx.arc(coord.x, coord.y, radius + 10, 0, 2 * Math.PI);
      ctx.fillStyle = "rgba(239, 68, 68, 0.3)";
      ctx.fill();

      if (alpha > 0.05) {
        const ventDirDeg = parseFloat(document.getElementById("inputAdvVentDir")?.value) || 0;
        const rad = ventDirDeg * Math.PI / 180.0;
        ctx.save();
        ctx.translate(coord.x, coord.y);
        ctx.rotate(rad);
        ctx.beginPath();
        ctx.moveTo(0, 0);
        ctx.lineTo(radius * 2.2, -radius * 0.8);
        ctx.lineTo(radius * 2.2, radius * 0.8);
        ctx.closePath();
        ctx.fillStyle = "rgba(249, 115, 22, 0.42)";
        ctx.fill();
        ctx.restore();
      }
    }

    // Geometri Çizimi
    if (isPrismatic) {
      // Prizmatik hücre dikdörtgeni + kutup başları
      const pw = radius * 2.6;
      const ph = radius * 1.5;
      ctx.fillStyle = fillColor;
      ctx.fillRect(coord.x - pw / 2, coord.y - ph / 2, pw, ph);

      ctx.fillStyle = "#e2e8f0";
      ctx.fillRect(coord.x - pw * 0.34, coord.y - ph / 2 - 3, 7, 3);
      ctx.fillStyle = "#f59e0b";
      ctx.fillRect(coord.x + pw * 0.34 - 7, coord.y - ph / 2 - 3, 7, 3);

      // Seçim Çerçevesi
      ctx.lineWidth = (id === state.selectedCellId) ? 3 : (id === triggerCellId ? 2.5 : 1.2);
      ctx.strokeStyle = (id === state.selectedCellId) ? "#38bdf8" : (id === triggerCellId ? "#f43f5e" : "rgba(255,255,255,0.25)");
      ctx.strokeRect(coord.x - pw / 2, coord.y - ph / 2, pw, ph);
    } else if (isPouch) {
      // Pouch (Kese) hücre yuvarlatılmış dikdörtgen + elektrot kulakçıkları
      const pw = radius * 3.0;
      const ph = radius * 1.2;
      ctx.fillStyle = fillColor;
      ctx.beginPath();
      if (ctx.roundRect) {
        ctx.roundRect(coord.x - pw / 2, coord.y - ph / 2, pw, ph, 4);
      } else {
        ctx.rect(coord.x - pw / 2, coord.y - ph / 2, pw, ph);
      }
      ctx.fill();

      // Kulakçıklar (Tabs)
      ctx.fillStyle = "#cbd5e1";
      ctx.fillRect(coord.x - pw / 2 - 4, coord.y - 4, 4, 8);
      ctx.fillStyle = "#f59e0b";
      ctx.fillRect(coord.x + pw / 2, coord.y - 4, 4, 8);

      ctx.lineWidth = (id === state.selectedCellId) ? 3 : (id === triggerCellId ? 2.5 : 1.2);
      ctx.strokeStyle = (id === state.selectedCellId) ? "#38bdf8" : (id === triggerCellId ? "#f43f5e" : "rgba(255,255,255,0.25)");
      ctx.stroke();
    } else {
      // Silindirik Hücre
      if (isCoreShell) {
        ctx.beginPath();
        ctx.arc(coord.x, coord.y, radius, 0, 2 * Math.PI);
        ctx.fillStyle = fillColor;
        ctx.fill();

        ctx.beginPath();
        ctx.arc(coord.x, coord.y, radius * 0.65, 0, 2 * Math.PI);
        ctx.fillStyle = coreColor;
        ctx.fill();
      } else {
        ctx.beginPath();
        ctx.arc(coord.x, coord.y, radius, 0, 2 * Math.PI);
        ctx.fillStyle = fillColor;
        ctx.fill();
      }

      ctx.lineWidth = (id === state.selectedCellId) ? 3 : (id === triggerCellId ? 2.5 : 1.5);
      ctx.strokeStyle = (id === state.selectedCellId) ? "#38bdf8" : (id === triggerCellId ? "#f43f5e" : "rgba(255,255,255,0.25)");
      ctx.stroke();
    }

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
  renderSubReactionTable(false);
}

function getDefaultSubReactionsForChem(chemId) {
  const chem = state.loadedChemistries[chemId];
  if (chem && Array.isArray(chem.sub_reactions) && chem.sub_reactions.length > 0) {
    return chem.sub_reactions.map(sr => ({
      key: sr.key,
      name: sr.name,
      A_per_s: Number(sr.A_per_s ?? sr.A ?? 1e14),
      Ea_kJ_per_mol: Number(sr.Ea_kJ_per_mol ?? ((sr.Ea_J_per_mol || 130000) / 1000)),
      delta_H_J_per_g: Number(sr.delta_H_J_per_g ?? ((sr.delta_H_J_per_kg ?? 500000) / 1000)),
      n: Number(sr.n ?? 1.0),
      m_autocatalytic: Number(sr.m_autocatalytic ?? 0.0),
      T_onset_K: Number(sr.T_onset_K ?? 373.15)
    }));
  }
  const low = String(chemId || "").toLowerCase();
  const isLfp = low.includes("lfp");
  const is811 = low.includes("811") || low.includes("nca");
  return [
    { key: "sei_decomposition", name: "1. SEI Bozunumu", A_per_s: 1.67e15, Ea_kJ_per_mol: 135.0, delta_H_J_per_g: 257.0, n: 1.0, m_autocatalytic: 0.0, T_onset_K: 353.15 },
    { key: "anode_electrolyte", name: "2. Anot-Elektrolit", A_per_s: 2.5e13, Ea_kJ_per_mol: 135.0, delta_H_J_per_g: 850.0, n: 1.0, m_autocatalytic: 0.0, T_onset_K: 393.15 },
    { key: "separator_melting", name: "3. Separatör (Endo)", A_per_s: 1.5e16, Ea_kJ_per_mol: 138.0, delta_H_J_per_g: -48.0, n: 1.0, m_autocatalytic: 0.0, T_onset_K: 403.15 },
    { key: "cathode_decomposition", name: "4. Katot Bozunumu", A_per_s: isLfp ? 2.0e11 : (is811 ? 1.8e13 : 6.67e12), Ea_kJ_per_mol: isLfp ? 148.0 : (is811 ? 139.0 : 144.0), delta_H_J_per_g: isLfp ? 210.0 : (is811 ? 780.0 : 620.0), n: 1.0, m_autocatalytic: 0.75, T_onset_K: isLfp ? 488.15 : (is811 ? 433.15 : 448.15) }
  ];
}

function renderSubReactionTable(forceReset = false) {
  const tbody = document.getElementById("subReactionTableBody");
  if (!tbody) return;
  if (!forceReset && tbody.children.length === 4) return;

  const chemId = document.getElementById("selectChemistry")?.value;
  const subs = getDefaultSubReactionsForChem(chemId);
  const shortLabels = {
    sei_decomposition: "SEI",
    anode_electrolyte: "Anot",
    separator_melting: "Separatör",
    cathode_decomposition: "Katot"
  };

  tbody.innerHTML = "";
  subs.forEach((sr, idx) => {
    const tr = document.createElement("tr");
    tr.dataset.key = sr.key;
    tr.dataset.name = sr.name;
    tr.dataset.n = sr.n;
    tr.dataset.m = sr.m_autocatalytic;
    tr.dataset.tonset = sr.T_onset_K;
    const isEndo = sr.delta_H_J_per_g < 0;
    const labelCol = isEndo ? "#38bdf8" : "#e2e8f0";
    tr.innerHTML = `
      <td style="font-weight:700; color:${labelCol}; white-space:nowrap;" title="${sr.name}">
        ${shortLabels[sr.key] || `#${idx + 1}`}${isEndo ? ' ❄️' : ''}
      </td>
      <td><input type="text" class="sub-rxn-a" value="${sr.A_per_s.toExponential(2)}"></td>
      <td><input type="number" step="0.5" class="sub-rxn-ea" value="${sr.Ea_kJ_per_mol.toFixed(1)}"></td>
      <td><input type="number" step="5" class="sub-rxn-dh" value="${sr.delta_H_J_per_g.toFixed(0)}"></td>
    `;
    tbody.appendChild(tr);
  });
}

function collectCustomSubReactions() {
  const tbody = document.getElementById("subReactionTableBody");
  if (!tbody || tbody.children.length === 0) return null;
  const list = [];
  Array.from(tbody.children).forEach(tr => {
    const aVal = parseFloat(tr.querySelector(".sub-rxn-a")?.value);
    const eaKj = parseFloat(tr.querySelector(".sub-rxn-ea")?.value);
    const dhJg = parseFloat(tr.querySelector(".sub-rxn-dh")?.value);
    if (!Number.isNaN(aVal) && !Number.isNaN(eaKj) && !Number.isNaN(dhJg)) {
      list.push({
        key: tr.dataset.key,
        name: tr.dataset.name,
        A_per_s: aVal,
        Ea_J_per_mol: eaKj * 1000.0,
        delta_H_J_per_kg: dhJg * 1000.0,
        n: parseFloat(tr.dataset.n || "1.0"),
        m_autocatalytic: parseFloat(tr.dataset.m || "0.0"),
        T_onset_K: parseFloat(tr.dataset.tonset || "373.15")
      });
    }
  });
  return list.length > 0 ? list : null;
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
    soc_percent: parseFloat(formData.get("soc_percent") || 100),
    isc_resistance_ohm: parseFloat(formData.get("isc_resistance_ohm") || 0.05),
    oven_target_temp_C: formData.get("oven_target_temp_C") ? parseFloat(formData.get("oven_target_temp_C")) : null,
    oven_ramp_C_per_min: parseFloat(formData.get("oven_ramp_C_per_min") || 5.0),
    enclosure_free_volume_liters: formData.get("enclosure_free_volume_liters") ? parseFloat(formData.get("enclosure_free_volume_liters")) : null,
    vent_valve_area_cm2: parseFloat(formData.get("vent_valve_area_cm2") || 2.0),
    vent_burst_pressure_kpa: parseFloat(formData.get("vent_burst_pressure_kpa") || 35.0),
    simulation_time_s: parseFloat(formData.get("simulation_time_s")),
    num_output_points: 200,

    // Gelişmiş Fizik (Aşama 1)
    advanced_physics_enabled: advEnabled,
    nodal_model: advEnabled && formData.get("nodal_model") ? formData.get("nodal_model") : "lumped",
    kinetics_model: advEnabled && formData.get("kinetics_model") ? formData.get("kinetics_model") : "single_step",
    ejecta_mass_loss_ratio: advEnabled && formData.get("ejecta_mass_loss_ratio") ? (parseFloat(formData.get("ejecta_mass_loss_ratio")) / 100.0) : 0.0,
    vent_direction_deg: advEnabled && formData.get("vent_direction_deg") ? parseFloat(formData.get("vent_direction_deg")) : null,
    custom_A_pre_exponential: advEnabled && formData.get("custom_A_pre_exponential") ? parseFloat(formData.get("custom_A_pre_exponential")) : null,
    custom_Ea_J_per_mol: advEnabled && formData.get("custom_Ea_J_per_mol") ? parseFloat(formData.get("custom_Ea_J_per_mol")) : null,
    custom_delta_H_J_per_g: advEnabled && formData.get("custom_delta_H_J_per_g") ? parseFloat(formData.get("custom_delta_H_J_per_g")) : null,
    custom_reaction_order_n: advEnabled && formData.get("custom_reaction_order_n") ? parseFloat(formData.get("custom_reaction_order_n")) : 1.0,
    custom_active_mass_ratio: advEnabled && formData.get("custom_active_mass_ratio") ? parseFloat(formData.get("custom_active_mass_ratio")) : null,
    custom_sub_reactions: (advEnabled && formData.get("kinetics_model") === "multi_reaction") ? collectCustomSubReactions() : null,
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

function generateClientTaskId(prefix = "task") {
  return `${prefix}_${Date.now()}_${Math.random().toString(36).substring(2, 8)}`;
}

function attachTaskProgressStream(taskId, onUpdate) {
  if (typeof EventSource === "undefined" || !taskId) {
    return () => {};
  }
  const es = new EventSource(`/api/tasks/${encodeURIComponent(taskId)}/stream`);
  es.onmessage = (evt) => {
    try {
      const payload = JSON.parse(evt.data);
      if (onUpdate) onUpdate(payload);
      if (payload.status === "COMPLETED" || payload.status === "FAILED") {
        es.close();
      }
    } catch (e) {
      // ignore parse errors
    }
  };
  es.onerror = () => {
    es.close();
  };
  return () => es.close();
}

async function handleRunDesignStudy() {
  const btn = document.getElementById("btnRunDesignStudy");
  const statusBox = document.getElementById("studyStatusBox");
  const progText = document.getElementById("studyProgressText");
  const progPct = document.getElementById("studyProgressPct");
  const progFill = document.getElementById("studyProgressFill");
  const results1D = document.getElementById("studyResultsContainer");
  const results2D = document.getElementById("study2DResultsContainer");
  const resultsTornado = document.getElementById("studyTornadoResultsContainer");

  const studyMode = document.getElementById("selectStudyMode")?.value || "1d_pareto";
  const taskId = generateClientTaskId("study");

  btn.disabled = true;
  btn.innerHTML = '<span class="btn-icon">⏳</span> Paralel Motor Çözüyor...';
  statusBox.style.display = "block";
  if (progText) progText.textContent = "⏳ Paralel işçi havuzu başlatılıyor...";
  if (progPct) progPct.textContent = "0%";
  if (progFill) progFill.style.width = "0%";
  if (results1D) results1D.style.display = "none";
  if (results2D) results2D.style.display = "none";
  if (resultsTornado) resultsTornado.style.display = "none";

  const closeStream = attachTaskProgressStream(taskId, (st) => {
    const pct = Math.round(st.progress_percent || 0);
    if (progText) progText.textContent = `⚡ ${st.message || "Paralel çözülüyor..."}`;
    if (progPct) progPct.textContent = `${pct}%`;
    if (progFill) progFill.style.width = `${pct}%`;
  });

  const baseConfig = buildSimulationPayload();

  try {
    if (studyMode === "2d_grid") {
      const paramX = document.getElementById("selectGridParamX").value;
      const paramY = document.getElementById("selectGridParamY").value;
      const valuesX = document.getElementById("inputGridValuesX").value
        .split(",").map(s => parseFloat(s.trim())).filter(n => !Number.isNaN(n));
      const valuesY = document.getElementById("inputGridValuesY").value
        .split(",").map(s => parseFloat(s.trim())).filter(n => !Number.isNaN(n));
      if (valuesX.length < 2 || valuesY.length < 2) {
        throw new Error("2D matris taraması için X ve Y eksenlerinde en az 2'şer sayısal değer girilmelidir.");
      }

      const res = await fetch("/api/simulations/design-study-2d", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          base_config: baseConfig,
          param_x: paramX,
          values_x: valuesX,
          param_y: paramY,
          values_y: valuesY,
          task_id: taskId
        })
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "2D tasarım taraması çözülemedi.");
      }
      const data = await res.json();
      render2DGridStudyResults(data);
    } else if (studyMode === "tornado_oat") {
      const pert = parseFloat(document.getElementById("inputTornadoPerturb")?.value) || 20.0;
      const res = await fetch("/api/simulations/sensitivity", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          base_config: baseConfig,
          perturbation_percent: pert,
          task_id: taskId
        })
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Tornado hassasiyet analizi çözülemedi.");
      }
      const data = await res.json();
      renderTornadoResults(data);
    } else {
      const sweepType = document.getElementById("selectSweepType").value;
      const wSafety = (parseFloat(document.getElementById("inputSweepWSafety")?.value) || 60) / 100.0;
      const wMass = (parseFloat(document.getElementById("inputSweepWMass")?.value) || 40) / 100.0;

      const res = await fetch("/api/simulations/design-study", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sweep_type: sweepType,
          base_config: baseConfig,
          w_safety: wSafety,
          w_mass: wMass,
          task_id: taskId
        })
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Tasarım çalışması çözülemedi.");
      }
      const data = await res.json();
      renderDesignStudyResults(data);
    }
  } catch (err) {
    alert(`Tasarım Çalışması Hatası: ${err.message}`);
    console.error(err);
  } finally {
    closeStream();
    btn.disabled = false;
    btn.innerHTML = '<span class="btn-icon">📊</span> Analizi Paralel Motorla Başlat';
    statusBox.style.display = "none";
  }
}

function render2DGridStudyResults(data) {
  const container = document.getElementById("study2DResultsContainer");
  const wrapper = document.getElementById("study2DGridWrapper");
  if (!container || !wrapper) return;

  const vxList = data.values_x || [];
  const vyList = data.values_y || [];
  const cases = data.cases || [];

  let html = `<table class="heatmap-2d-table"><thead><tr><th>${data.param_x} \\ ${data.param_y}</th>`;
  vyList.forEach(vy => {
    html += `<th>${vy}</th>`;
  });
  html += `</tr></thead><tbody>`;

  vxList.forEach((vx, xi) => {
    html += `<tr><th style="text-align:right; white-space:nowrap;">${vx}</th>`;
    vyList.forEach((vy, yi) => {
      const risk = data.matrix_risk_score[xi][yi];
      const peakT = data.matrix_peak_temp_C[xi][yi];
      const matchCase = cases.find(c => String(c.x_val) === String(vx) && String(c.y_val) === String(vy));
      const jobId = matchCase ? matchCase.job_id : "";
      let bg = "rgba(16, 185, 129, 0.28)";
      let txtCol = "#6ee7b7";
      if (risk > 60) {
        bg = "rgba(239, 68, 68, 0.35)";
        txtCol = "#fca5a5";
      } else if (risk > 25) {
        bg = "rgba(245, 158, 11, 0.30)";
        txtCol = "#fde68a";
      }
      html += `
        <td class="heatmap-2d-cell" style="background:${bg};" onclick="${jobId ? `loadDesignCase('${jobId}')` : ''}" title="Tmax: ${peakT.toFixed(1)}°C | Risk: ${risk}/100 (Tıklayarak yükle)">
          <div style="font-weight:800; color:${txtCol}; font-size:11px;">Risk: ${risk}</div>
          <div style="font-size:9px; color:#e2e8f0;">${Math.round(peakT)}°C</div>
        </td>
      `;
    });
    html += `</tr>`;
  });
  html += `</tbody></table>`;
  wrapper.innerHTML = html;
  container.style.display = "block";
}

function renderTornadoResults(data) {
  const container = document.getElementById("studyTornadoResultsContainer");
  const topText = document.getElementById("tornadoTopParamText");
  const canvas = document.getElementById("tornadoChart");
  if (!container || !canvas) return;

  const ranked = data.parameters_ranked || [];
  if (topText) {
    if (ranked.length > 0) {
      topText.textContent = `${ranked[0].param_name} (ΔT Salınımı: ${ranked[0].temp_swing_C.toFixed(1)} °C | Baz Tmax: ${data.baseline_peak_temp_C.toFixed(1)} °C)`;
    } else {
      topText.textContent = "Duyarlılık farkı oluşmadı.";
    }
  }

  if (state.tornadoChart) state.tornadoChart.destroy();
  const ctx = canvas.getContext("2d");
  const labels = ranked.map(item => item.param_name);
  const lowDeltas = ranked.map(item => item.delta_temp_low_C);
  const highDeltas = ranked.map(item => item.delta_temp_high_C);

  state.tornadoChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: "Düşük Sapma (-% Parametre)",
          data: lowDeltas,
          backgroundColor: "rgba(56, 189, 248, 0.75)",
          borderColor: "#38bdf8",
          borderWidth: 1
        },
        {
          label: "Yüksek Sapma (+% Parametre)",
          data: highDeltas,
          backgroundColor: "rgba(249, 115, 22, 0.75)",
          borderColor: "#f97316",
          borderWidth: 1
        }
      ]
    },
    options: {
      indexAxis: "y",
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: "#cbd5e1", boxWidth: 10, font: { size: 9 } } }
      },
      scales: {
        x: {
          title: { display: true, text: "ΔT_peak Baz Değişimi (°C)", color: "#94a3b8", font: { size: 9 } },
          ticks: { color: "#94a3b8", font: { size: 9 } },
          grid: { color: "#1e293b" }
        },
        y: {
          ticks: { color: "#e2e8f0", font: { size: 9 } },
          grid: { color: "#1e293b" }
        }
      }
    }
  });
  container.style.display = "block";
}

function renderDesignStudyResults(data) {
  const container = document.getElementById("studyResultsContainer");
  const recText = document.getElementById("studyRecText");
  const tbody = document.getElementById("studyTableBody");

  const bestCase = data.cases[data.recommended_case_index];
  recText.textContent = data.recommended_reason || `${bestCase.case_name} → ${bestCase.param_value}`;

  tbody.innerHTML = "";
  data.cases.forEach((c) => {
    const tr = document.createElement("tr");
    tr.className = `design-study-row ${c.is_recommended ? "recommended" : ""}`;

    const recBadge = c.is_recommended ? '<span class="rec-badge">★ KNEE POINT</span>' : '';
    const riskColor = c.risk_score_100 <= 25 ? '#10b981' : (c.risk_score_100 <= 60 ? '#f59e0b' : '#ef4444');
    const massStr = c.module_mass_kg ? `${c.module_mass_kg.toFixed(2)} kg` : '--';
    const deltaMass = c.mass_penalty_index_percent || 0.0;
    const deltaMassColor = deltaMass > 0 ? '#f87171' : (deltaMass < 0 ? '#34d399' : '#94a3b8');
    const deltaMassStr = `${deltaMass > 0 ? '+' : ''}${deltaMass.toFixed(1)}%`;
    const paretoBadge = c.is_pareto_optimal 
      ? '<span style="color:#38bdf8; font-weight:700; font-size:9px; background:rgba(56,189,248,0.15); padding:2px 6px; border-radius:3px;">★ OPTİMAL</span>' 
      : '<span style="color:#64748b; font-size:9px;">○ Domine</span>';

    tr.innerHTML = `
      <td style="font-weight:600;">${c.case_name} ${recBadge}</td>
      <td><span style="font-weight:700; color:${riskColor};">${c.risk_score_100}</span>/100</td>
      <td style="color:#cbd5e1; font-weight:600;">${massStr}</td>
      <td><span style="color:${deltaMassColor}; font-weight:600;">${deltaMassStr}</span></td>
      <td style="text-align:center;">${paretoBadge}</td>
      <td style="text-align:center;">
        <button type="button" class="btn-study-load" onclick="loadDesignCase('${c.job_id}')" title="Bu simülasyonu çalışma alanına yükle">
          🔍 İncele
        </button>
      </td>
    `;
    tbody.appendChild(tr);
  });

  drawParetoFrontCanvas(data);
  container.style.display = "block";
}

function drawParetoFrontCanvas(data) {
  const canvas = document.getElementById("paretoCanvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const w = canvas.width;
  const h = canvas.height;

  // Temizle
  ctx.fillStyle = "#090d16";
  ctx.fillRect(0, 0, w, h);

  const cases = data.cases;
  if (!cases || cases.length === 0) return;

  const masses = cases.map(c => c.module_mass_kg || 1.0);
  const risks = cases.map(c => c.risk_score_100 || 0.0);

  let minM = Math.min(...masses), maxM = Math.max(...masses);
  let minR = Math.min(...risks), maxR = Math.max(...risks);

  const padLeft = 36, padRight = 20, padTop = 22, padBottom = 24;
  const plotW = w - padLeft - padRight;
  const plotH = h - padTop - padBottom;

  if (Math.abs(maxM - minM) < 1e-4) { minM -= 0.5; maxM += 0.5; }
  if (Math.abs(maxR - minR) < 1e-4) { minR = 0; maxR = 100; }
  else { minR = Math.max(0, minR - 5); maxR = Math.min(100, maxR + 5); }

  const getX = (m) => padLeft + ((m - minM) / (maxM - minM)) * plotW;
  const getY = (r) => padTop + ((maxR - r) / (maxR - minR)) * plotH;

  // Kılavuz çizgileri
  ctx.strokeStyle = "#1e293b";
  ctx.lineWidth = 1;
  ctx.beginPath();
  for (let i = 0; i <= 3; i++) {
    const yVal = padTop + (plotH / 3) * i;
    ctx.moveTo(padLeft, yVal);
    ctx.lineTo(w - padRight, yVal);
  }
  ctx.stroke();

  // Eksen etiketleri
  ctx.fillStyle = "#64748b";
  ctx.font = "8px sans-serif";
  ctx.textAlign = "right";
  ctx.fillText(`${Math.round(maxR)}`, padLeft - 4, padTop + 8);
  ctx.fillText(`${Math.round(minR)}`, padLeft - 4, padTop + plotH);
  ctx.textAlign = "center";
  ctx.fillText(`${minM.toFixed(1)}kg`, padLeft + 12, h - 6);
  ctx.fillText(`${maxM.toFixed(1)}kg`, w - padRight - 12, h - 6);

  // Pareto Cephesi Çizgisi (Pareto optimal noktaları kütleye göre sıralı bağla)
  const paretoPoints = (data.pareto_front_indices || [])
    .map(idx => cases[idx])
    .filter(Boolean)
    .sort((a, b) => a.module_mass_kg - b.module_mass_kg);

  if (paretoPoints.length > 1) {
    ctx.beginPath();
    ctx.strokeStyle = "#0284c7";
    ctx.lineWidth = 1.8;
    ctx.setLineDash([4, 3]);
    paretoPoints.forEach((p, i) => {
      const px = getX(p.module_mass_kg);
      const py = getY(p.risk_score_100);
      if (i === 0) ctx.moveTo(px, py);
      else ctx.lineTo(px, py);
    });
    ctx.stroke();
    ctx.setLineDash([]);
  }

  // Noktaları çiz
  cases.forEach((c, idx) => {
    const px = getX(c.module_mass_kg);
    const py = getY(c.risk_score_100);
    const isKnee = idx === data.knee_point_index;
    const isPareto = c.is_pareto_optimal;

    if (isKnee) {
      // Glow halkası
      ctx.beginPath();
      ctx.arc(px, py, 9, 0, 2 * Math.PI);
      ctx.fillStyle = "rgba(16, 185, 129, 0.35)";
      ctx.fill();

      // Yeşil merkez
      ctx.beginPath();
      ctx.arc(px, py, 5, 0, 2 * Math.PI);
      ctx.fillStyle = "#10b981";
      ctx.fill();
      ctx.strokeStyle = "#ffffff";
      ctx.lineWidth = 1.5;
      ctx.stroke();

      // Etiket
      ctx.fillStyle = "#34d399";
      ctx.font = "bold 9px sans-serif";
      ctx.textAlign = "center";
      const shortName = c.case_name.split(' ')[0];
      ctx.fillText(`★ ${shortName}`, px, py - 11);
    } else if (isPareto) {
      // Pareto Optimal nokta (mavi dolu)
      ctx.beginPath();
      ctx.arc(px, py, 4.5, 0, 2 * Math.PI);
      ctx.fillStyle = "#38bdf8";
      ctx.fill();
      ctx.strokeStyle = "#ffffff";
      ctx.lineWidth = 1;
      ctx.stroke();
    } else {
      // Domine edilen nokta (gri boş)
      ctx.beginPath();
      ctx.arc(px, py, 3.5, 0, 2 * Math.PI);
      ctx.fillStyle = "#334155";
      ctx.fill();
      ctx.strokeStyle = "#64748b";
      ctx.lineWidth = 1;
      ctx.stroke();
    }
  });
}

/* ================= 6b. AŞAMA 2: KANIT & VALİDASYON MOTORU VE MONTE CARLO UQ ================= */

async function handleRunValidationCompare() {
  const btn = document.getElementById("btnRunValidationCompare");
  const csvArea = document.getElementById("textareaValidationCsv");
  const cellInput = document.getElementById("inputValCompareCell");

  const csvContent = csvArea.value.trim();
  if (!csvContent) {
    alert("Lütfen bir CSV dosyası seçin veya zaman-sıcaklık verilerini yapıştırın (time_s,temperature_C).");
    return;
  }

  const cellId = parseInt(cellInput.value, 10) || 0;

  btn.disabled = true;
  btn.innerHTML = '<span class="btn-icon">⏳</span> Kalibrasyon Karşılaştırılıyor...';

  try {
    let jobId = state.simulationData?.job_id;
    if (!jobId) {
      btn.innerHTML = '<span class="btn-icon">⏳</span> Temel Simülasyon Çözülüyor...';
      const basePayload = buildSimulationPayload();
      const runRes = await fetch("/api/simulations/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(basePayload)
      });
      if (!runRes.ok) {
        const err = await runRes.json();
        throw new Error(err.detail || "Simülasyon çalıştırılamadı.");
      }
      const runData = await runRes.json();
      jobId = runData.job_id;

      const fullRes = await fetch(`/api/simulations/${jobId}/results`);
      state.simulationData = await fullRes.json();
      renderSimulationResults(state.simulationData);
    }

    const payload = {
      job_id: jobId,
      csv_content: csvContent,
      cell_id: cellId
    };

    const compRes = await fetch("/api/validation/compare", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (!compRes.ok) {
      const err = await compRes.json();
      throw new Error(err.detail || "Validasyon karşılaştırma hatası.");
    }

    const compData = await compRes.json();
    state.validationResult = compData;
    renderValidationResults(compData);

    // Chart'ı güncelle ve modali göster
    if (state.simulationData) {
      renderChart(state.simulationData.simulation_result);
      const chartModal = document.getElementById("chartModal");
      if (chartModal) chartModal.style.display = "flex";
    }
  } catch (err) {
    alert(`Validasyon Hatası: ${err.message}`);
    console.error(err);
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<span class="btn-icon">🔬</span> Kalibre Et & Doğrula';
  }
}

function renderValidationResults(data) {
  const card = document.getElementById("validationResultCard");
  const badge = document.getElementById("valScoreBadge");
  const verdictText = document.getElementById("valVerdictText");
  const rmseVal = document.getElementById("valRmseVal");
  const deltaPeakVal = document.getElementById("valDeltaPeakVal");
  const deltaTimeVal = document.getElementById("valDeltaTimeVal");
  const peaksComp = document.getElementById("valPeaksComp");
  const treeBadge = document.getElementById("statusValidationBadge");

  card.style.display = "block";
  badge.textContent = `%${data.validation_score_percent.toFixed(1)}`;
  if (data.validation_score_percent >= 85) {
    badge.style.background = "#10b981";
  } else if (data.validation_score_percent >= 70) {
    badge.style.background = "#f59e0b";
  } else {
    badge.style.background = "#ef4444";
  }

  verdictText.textContent = data.regulatory_verdict;
  rmseVal.textContent = `${data.rmse_C.toFixed(2)} °C`;
  deltaPeakVal.textContent = `${data.delta_T_peak_C > 0 ? "+" : ""}${data.delta_T_peak_C.toFixed(1)} °C`;
  deltaTimeVal.textContent = `${data.delta_t_runaway_s > 0 ? "+" : ""}${data.delta_t_runaway_s.toFixed(2)} s`;
  peaksComp.textContent = `Sim: ${data.sim_peak_T_C.toFixed(0)}° / Deney: ${data.exp_peak_T_C.toFixed(0)}°`;

  if (treeBadge) {
    treeBadge.textContent = "✓";
    treeBadge.className = "tree-status status-ready";
  }
}

async function handleRunMonteCarlo() {
  const btn = document.getElementById("btnRunMonteCarlo");
  const statusBox = document.getElementById("mcStatusBox");
  const progText = document.getElementById("mcProgressText");
  const progPct = document.getElementById("mcProgressPct");
  const progFill = document.getElementById("mcProgressFill");
  const card = document.getElementById("mcResultCard");

  const samples = parseInt(document.getElementById("inputMcSamples")?.value, 10) || 15;
  const variance = parseFloat(document.getElementById("inputMcVariance")?.value) || 5.0;
  const taskId = generateClientTaskId("mc");

  btn.disabled = true;
  btn.innerHTML = '<span class="btn-icon">⏳</span> Monte Carlo Paralel Çözülüyor...';
  if (statusBox) statusBox.style.display = "block";
  if (progText) progText.textContent = `⏳ 0/${samples} örneklem başlatılıyor...`;
  if (progPct) progPct.textContent = "0%";
  if (progFill) progFill.style.width = "0%";
  if (card) card.style.display = "none";

  const closeStream = attachTaskProgressStream(taskId, (st) => {
    const pct = Math.round(st.progress_percent || 0);
    if (progText) progText.textContent = `🎲 ${st.message || "Monte Carlo çözülüyor..."}`;
    if (progPct) progPct.textContent = `${pct}%`;
    if (progFill) progFill.style.width = `${pct}%`;
  });

  const baseConfig = buildSimulationPayload();
  const payload = {
    base_config: baseConfig,
    n_samples: samples,
    variance_percent: variance,
    task_id: taskId
  };

  try {
    const res = await fetch("/api/simulations/monte-carlo-uq", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Monte Carlo UQ analizi başarısız oldu.");
    }

    const mcData = await res.json();
    state.monteCarloResult = mcData;
    renderMonteCarloResults(mcData);

    if (state.simulationData) {
      renderChart(state.simulationData.simulation_result);
      const chartModal = document.getElementById("chartModal");
      if (chartModal) chartModal.style.display = "flex";
    }
  } catch (err) {
    alert(`Monte Carlo Hatası: ${err.message}`);
    console.error(err);
  } finally {
    closeStream();
    btn.disabled = false;
    btn.innerHTML = '<span class="btn-icon">🎲</span> Monte Carlo UQ Analizini Çalıştır';
    if (statusBox) statusBox.style.display = "none";
  }
}

function renderMonteCarloResults(data) {
  const card = document.getElementById("mcResultCard");
  const summaryText = document.getElementById("mcSummaryText");
  const valP10 = document.getElementById("mcValP10");
  const valP50 = document.getElementById("mcValP50");
  const valP90 = document.getElementById("mcValP90");
  const valCiWidth = document.getElementById("mcValCiWidth");

  card.style.display = "block";
  summaryText.textContent = data.summary_statement;
  valP10.textContent = `${data.p10_peak_temp_C.toFixed(1)} °C`;
  valP50.textContent = `${data.p50_peak_temp_C.toFixed(1)} °C`;
  valP90.textContent = `${data.p90_peak_temp_C.toFixed(1)} °C`;
  valCiWidth.textContent = `±${(data.confidence_interval_width_C / 2.0).toFixed(1)} °C`;
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
  const modMass = evalData.module_mass_kg ?? simRes.pack_metrics?.module_mass_kg;
  const valMassEl = document.getElementById("valModuleMass");
  if (valMassEl) {
    valMassEl.textContent = modMass != null ? `${Number(modMass).toFixed(2)} kg` : "-- kg";
  }
  document.getElementById("valHash").textContent = simRes.config_hash.substring(0, 20) + "...";

  // 2b. Gaz Salınımı & Patlama Tehlikesi Kartı (NFPA 68)
  const gh = simRes.gas_hazard_summary;
  if (gh) {
    const enc = gh.enclosure_analysis;
    const elTotal = document.getElementById("valGasTotalL");
    const elMixLel = document.getElementById("valGasMixLel");
    const elPress = document.getElementById("valGasPeakPressure");
    const elMinVent = document.getElementById("valGasMinVent");
    const elLelBadge = document.getElementById("valGasLelBadge");

    if (elTotal) elTotal.textContent = `${Number(gh.total_gas_released_stp_L || 0).toFixed(1)} L`;
    if (elMixLel) elMixLel.textContent = `%${Number(gh.mixture_lel_percent || 0).toFixed(2)}`;
    if (enc) {
      if (elPress) elPress.textContent = `${Number(enc.peak_overpressure_kpa || 0).toFixed(1)} kPa`;
      if (elMinVent) elMinVent.textContent = `${Number(enc.recommended_min_vent_area_cm2 || 1.0).toFixed(1)} cm²`;
      if (elLelBadge) {
        const peakLel = Number(enc.peak_lel_ratio_percent || 0);
        elLelBadge.textContent = `${peakLel.toFixed(0)}% LEL${peakLel >= 100 ? " (PATLAYICI)" : ""}`;
        elLelBadge.className = peakLel >= 100 ? "reg-badge-fail" : (peakLel >= 25 ? "reg-badge-warn" : "reg-badge-pass");
      }
    }
  }

  // 2c. Regülasyon Ön-Uyumluluk Matrisi (GB 38031 5-Dk Kuralı / UL 9540A / UN 38.3)
  const reg = evalData.regulatory_compliance;
  if (reg) {
    const setRegBadge = (badgeId, descId, obj) => {
      if (!obj) return;
      const bEl = document.getElementById(badgeId);
      const dEl = document.getElementById(descId);
      if (bEl) {
        bEl.textContent = obj.passed ? "✓ UYGUN" : "✕ RİSKLİ";
        bEl.className = obj.passed ? "reg-badge-pass" : "reg-badge-fail";
      }
      if (dEl && obj.verdict) {
        dEl.textContent = obj.verdict;
      }
    };
    setRegBadge("regBadgeGb38031", "regDescGb38031", reg.gb_38031_5min_egress);
    setRegBadge("regBadgeUl9540a", "regDescUl9540a", reg.ul_9540a_unit_level);
    setRegBadge("regBadgeUn383", "regDescUn383", reg.un_383_thermal_abuse);
  }

  // PDF İndirme Butonları
  const pdfUrl = `/api/simulations/${data.job_id}/report`;
  const topReportBtn = document.getElementById("btnDownloadReport");
  const sideReportBtn = document.getElementById("btnSideDownloadReport");
  topReportBtn.href = pdfUrl;
  topReportBtn.style.display = "inline-flex";
  sideReportBtn.href = pdfUrl;
  sideReportBtn.style.display = "inline-flex";

  // Aşama 4: Dışa Aktarma ve Kriptografik Denetim Butonları
  const csvBtn = document.getElementById("btnSideDownloadCsv");
  const npzBtn = document.getElementById("btnSideDownloadNpz");
  const certBtn = document.getElementById("btnSideAuditCert");
  const exportGroup = document.getElementById("exportActionGroup");

  if (csvBtn) csvBtn.href = `/api/simulations/${data.job_id}/export?format=csv`;
  if (npzBtn) npzBtn.href = `/api/simulations/${data.job_id}/export?format=npz`;
  if (exportGroup) exportGroup.style.display = "flex";
  if (certBtn) certBtn.style.display = "block";

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
  renderDrawerChart(state.drawerActiveTab);

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
  const drawerCursor = document.getElementById("drawerTimeCursor");
  if (drawerCursor) {
    drawerCursor.textContent = `t = ${timeSec.toFixed(2)} s`;
  }

  updateCellStyles();
  draw2DCanvas();
  updateCellInspectorUI();
  if (state.drawerChart) {
    state.drawerChart.update("none");
  }
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

function interpolateSeries(sourceTimes, sourceVals, targetTimes) {
  if (!sourceTimes || sourceTimes.length === 0 || !sourceVals || sourceVals.length === 0) return [];
  if (sourceTimes.length === 1) return targetTimes.map(() => sourceVals[0]);

  return targetTimes.map(t => {
    if (t <= sourceTimes[0]) return sourceVals[0];
    if (t >= sourceTimes[sourceTimes.length - 1]) return sourceVals[sourceVals.length - 1];
    let i = 0;
    while (i < sourceTimes.length - 1 && sourceTimes[i + 1] < t) i++;
    const t0 = sourceTimes[i], t1 = sourceTimes[i + 1];
    const y0 = sourceVals[i], y1 = sourceVals[i + 1];
    if (t1 === t0) return y0;
    return y0 + (t - t0) * (y1 - y0) / (t1 - t0);
  });
}

function renderChart(simRes) {
  const ctx = document.getElementById("tempChart").getContext("2d");
  if (state.tempChart) state.tempChart.destroy();

  const timePts = simRes.time_points_s;
  const triggerId = state.simulationData.request_config.trigger_cell_id;
  const datasets = [];

  // Seçili kimyanın dinamik eşik çizgileri
  const { tOnset: onsetTemp, tTrigger: triggerTemp } = getChemistryThresholds();
  datasets.push({
    label: `T_onset (${Math.round(onsetTemp)}°C)`,
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

  // Monte Carlo UQ Zarfı Overlay (Alt katman)
  if (state.monteCarloResult && state.monteCarloResult.time_points_s) {
    const mc = state.monteCarloResult;
    const p90Interp = interpolateSeries(mc.time_points_s, mc.p90_temperature_history_C, timePts);
    const p50Interp = interpolateSeries(mc.time_points_s, mc.p50_temperature_history_C, timePts);
    const p10Interp = interpolateSeries(mc.time_points_s, mc.p10_temperature_history_C, timePts);

    datasets.push({
      label: "🎲 Monte Carlo P90 (Üst Sınır)",
      data: p90Interp,
      borderColor: "rgba(248, 113, 113, 0.85)",
      borderWidth: 1.8,
      borderDash: [3, 3],
      pointRadius: 0,
      fill: false
    });
    datasets.push({
      label: "🎲 Monte Carlo P50 (Medyan)",
      data: p50Interp,
      borderColor: "rgba(167, 139, 250, 1.0)",
      borderWidth: 2.2,
      pointRadius: 0,
      fill: false
    });
    datasets.push({
      label: "🎲 Monte Carlo P10 (Alt Sınır)",
      data: p10Interp,
      borderColor: "rgba(52, 211, 153, 0.85)",
      borderWidth: 1.8,
      borderDash: [3, 3],
      pointRadius: 0,
      fill: false
    });
  }

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

  // Validasyon: Deneysel Sensör Eğrisi Overlay (Üst katman)
  if (state.validationResult && state.validationResult.aligned_time_points) {
    const val = state.validationResult;
    const expInterp = interpolateSeries(val.aligned_time_points, val.experimental_temperatures, timePts);
    datasets.push({
      label: "🔬 Deneysel Sensör (Laboratuvar)",
      data: expInterp,
      borderColor: "#06b6d4",
      backgroundColor: "transparent",
      borderWidth: 2.5,
      borderDash: [5, 4],
      pointRadius: 0,
      fill: false
    });
  }

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

  // Aşama 4: Kriptografik Denetim Sertifikası Modalı
  const auditModal = document.getElementById("auditCertModal");
  const btnOpenAudit = document.getElementById("btnSideAuditCert");
  const btnCloseAudit = document.getElementById("closeAuditCertModal");
  const btnCloseAuditBottom = document.getElementById("btnCloseAuditCert");

  if (btnOpenAudit) {
    btnOpenAudit.addEventListener("click", async () => {
      if (!state.simulationData) return;
      const jobId = state.simulationData.job_id;
      try {
        const res = await fetch(`/api/simulations/${jobId}/audit-certificate`);
        if (!res.ok) throw new Error("Sertifika alınamadı.");
        const cert = await res.json();

        document.getElementById("modalCertTitle").textContent = cert.certificate_id;
        document.getElementById("modalCertSha").textContent = cert.config_hash_sha256;
        document.getElementById("modalCertGit").textContent = cert.git_commit_sha;
        document.getElementById("modalCertSolver").textContent = cert.solver_engine;
        document.getElementById("modalCertTime").textContent = cert.timestamp_created_utc;
        document.getElementById("modalCertLib").textContent = cert.library_validation_source;
        document.getElementById("modalCertUrn").textContent = cert.verification_urn;

        if (auditModal) auditModal.style.display = "flex";
      } catch (err) {
        alert(`Denetim Sertifikası Hatası: ${err.message}`);
      }
    });
  }

  [btnCloseAudit, btnCloseAuditBottom].forEach(b => {
    if (b) b.addEventListener("click", () => {
      if (auditModal) auditModal.style.display = "none";
    });
  });

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

  // Özel Format Türü Değişimi (Silindirik vs Prizmatik / Pouch) ve Form Gönderimi
  const cfTypeSelect = document.getElementById("cf_type");
  const cfRadiusGroup = document.getElementById("cfRadiusGroup");
  const cfPlanarFields = document.getElementById("cfPlanarFields");
  if (cfTypeSelect) {
    cfTypeSelect.addEventListener("change", (e) => {
      const isCyl = e.target.value === "cylindrical";
      if (cfRadiusGroup) cfRadiusGroup.style.display = isCyl ? "block" : "none";
      if (cfPlanarFields) cfPlanarFields.style.display = isCyl ? "none" : "grid";
      const tInput = document.getElementById("cf_t");
      if (tInput) {
        if (e.target.value === "pouch") tInput.value = "0.15";
        else if (e.target.value === "prismatic") tInput.value = "0.8";
        else tInput.value = "0.3";
      }
    });
  }

  document.getElementById("formCustomFormat").addEventListener("submit", async (e) => {
    e.preventDefault();
    const fmtType = document.getElementById("cf_type")?.value || "cylindrical";
    const payload = {
      format_name: document.getElementById("cf_name").value,
      format_type: fmtType,
      radius_mm: fmtType === "cylindrical" ? (parseFloat(document.getElementById("cf_r").value) || 9.0) : null,
      width_mm: fmtType !== "cylindrical" ? (parseFloat(document.getElementById("cf_w")?.value) || 148.0) : null,
      thickness_mm: fmtType !== "cylindrical" ? (parseFloat(document.getElementById("cf_thick")?.value) || 15.0) : null,
      height_mm: parseFloat(document.getElementById("cf_h").value),
      mass_kg: parseFloat(document.getElementById("cf_mass").value),
      cp_J_per_kg_K: parseFloat(document.getElementById("cf_cp")?.value) || 1050.0,
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
      const dims = (f.type === "prismatic" || f.type === "pouch")
        ? `En: ${Math.round((f.width || 0.148) * 1000)}mm, Kalınlık: ${Math.round((f.thickness || f.depth || 0.015) * 1000)}mm, Boy: ${Math.round((f.height || 0.100) * 1000)}mm`
        : `Çap: ${Math.round((f.radius || 0.009) * 2000)}mm, Yükseklik: ${Math.round((f.height || 0.065) * 1000)}mm`;
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

/* ================= 9. FORM VE ŞABLON YÖNETİCİSİ (PRESETS & PROJECTS) ================= */

function applyConfigToForm(cfg) {
  if (!cfg) return;
  const setVal = (id, val) => {
    const el = document.getElementById(id);
    if (el && val !== undefined && val !== null) {
      el.value = val;
    }
  };
  const setChk = (id, val) => {
    const el = document.getElementById(id);
    if (el && val !== undefined && val !== null) {
      el.checked = !!val;
      el.dispatchEvent(new Event("change"));
    }
  };

  let fmtVal = cfg.cell_format;
  const fmtSelect = document.getElementById("selectFormat");
  if (fmtSelect && fmtVal) {
    if (!fmtSelect.querySelector(`option[value="${fmtVal}"]`)) {
      if (fmtVal === "prismatic" && fmtSelect.querySelector('option[value="Prismatic_50Ah"]')) fmtVal = "Prismatic_50Ah";
      else if (fmtVal === "pouch" && fmtSelect.querySelector('option[value="Pouch_60Ah"]')) fmtVal = "Pouch_60Ah";
      else if (fmtVal === "Prismatic_50Ah" && fmtSelect.querySelector('option[value="prismatic"]')) fmtVal = "prismatic";
      else if (fmtVal === "Pouch_60Ah" && fmtSelect.querySelector('option[value="pouch"]')) fmtVal = "pouch";
    }
  }
  setVal("selectFormat", fmtVal);
  setVal("inputRows", cfg.rows);
  setVal("inputCols", cfg.cols);
  setVal("inputSpacingX", cfg.spacing_x_mm);
  setVal("inputSpacingY", cfg.spacing_y_mm);
  setChk("checkboxStaggered", cfg.staggered);
  setVal("selectChemistry", cfg.chemistry_id);
  setVal("selectSeparator", cfg.separator_material_id || "");
  setVal("inputSepThickness", cfg.separator_thickness_mm);
  setVal("selectGapMaterial", cfg.gap_material_id || "air_gap");
  setVal("inputTamb", cfg.T_ambient_C);
  setVal("inputBusbar", cfg.busbar_conductance_W_per_K);
  setChk("checkboxCooling", cfg.active_cooling_enabled);
  setVal("inputHcool", cfg.h_cooling_plate_W_per_m2_K);
  setVal("inputTcool", cfg.T_coolant_C);
  setVal("inputSocPercent", cfg.soc_percent !== undefined ? cfg.soc_percent : 100);
  const socLbl = document.getElementById("lblSocPercent");
  if (socLbl) socLbl.textContent = `${cfg.soc_percent !== undefined ? cfg.soc_percent : 100}%`;
  setVal("inputTriggerCell", cfg.trigger_cell_id);
  setVal("selectTriggerMethod", cfg.trigger_method);
  const triggerSelect = document.getElementById("selectTriggerMethod");
  if (triggerSelect) triggerSelect.dispatchEvent(new Event("change"));
  setVal("inputTriggerPower", cfg.trigger_power_W);
  setVal("inputTriggerDuration", cfg.trigger_duration_s);
  setVal("inputTriggerInitialTemp", cfg.trigger_initial_temp_C);
  setVal("inputIscResistance", cfg.isc_resistance_ohm);
  setVal("inputOvenTarget", cfg.oven_target_temp_C);
  setVal("inputOvenRamp", cfg.oven_ramp_C_per_min);
  setVal("inputAdvFreeVol", cfg.enclosure_free_volume_liters);
  setVal("inputAdvVentArea", cfg.vent_valve_area_cm2);
  setVal("inputAdvBurstPress", cfg.vent_burst_pressure_kpa);
  setVal("inputSimTime", cfg.simulation_time_s);
  const simLbl = document.getElementById("lblSimTime");
  if (simLbl && cfg.simulation_time_s) simLbl.textContent = `${cfg.simulation_time_s} s`;

  setChk("checkboxAdvPhysics", cfg.advanced_physics_enabled);
  setVal("selectNodalModel", cfg.nodal_model);
  setVal("selectKineticsModel", cfg.kinetics_model);
  const kinSel = document.getElementById("selectKineticsModel");
  if (kinSel) kinSel.dispatchEvent(new Event("change"));
  if (cfg.ejecta_mass_loss_ratio !== undefined) {
    setVal("inputAdvMassLoss", cfg.ejecta_mass_loss_ratio * 100);
  }
  setVal("inputAdvVentDir", cfg.vent_direction_deg);
  setVal("inputAdvA", cfg.custom_A_pre_exponential ?? "");
  setVal("inputAdvEa", cfg.custom_Ea_J_per_mol ?? "");
  setVal("inputAdvDeltaH", cfg.custom_delta_H_J_per_g ?? "");
  setVal("inputAdvN", cfg.custom_reaction_order_n ?? 1.0);
  setVal("inputAdvRatio", cfg.custom_active_mass_ratio ?? "");
  setVal("inputAdvHvent", cfg.h_vent_W_per_m2_K ?? 100);
  setVal("inputAdvTgas", cfg.T_vent_gas_C ?? "");
  setVal("inputAdvEmissivity", cfg.surface_emissivity ?? 0.85);

  updatePackLayoutFromInputs();
  updateChemistryDetails();

  if (Array.isArray(cfg.custom_sub_reactions) && cfg.custom_sub_reactions.length > 0) {
    const tbody = document.getElementById("subReactionTableBody");
    if (tbody) {
      Array.from(tbody.children).forEach((tr, idx) => {
        const sr = cfg.custom_sub_reactions[idx];
        if (!sr) return;
        const aIn = tr.querySelector(".sub-rxn-a");
        const eaIn = tr.querySelector(".sub-rxn-ea");
        const dhIn = tr.querySelector(".sub-rxn-dh");
        if (aIn && sr.A_per_s != null) aIn.value = Number(sr.A_per_s).toExponential(2);
        if (eaIn && sr.Ea_J_per_mol != null) eaIn.value = (Number(sr.Ea_J_per_mol) / 1000.0).toFixed(1);
        if (dhIn && sr.delta_H_J_per_kg != null) dhIn.value = (Number(sr.delta_H_J_per_kg) / 1000.0).toFixed(0);
      });
    }
  }
}

async function initPresets() {
  const selectPreset = document.getElementById("selectPreset");
  if (!selectPreset) return;

  try {
    const res = await fetch("/api/presets");
    if (res.ok) {
      const data = await res.json();
      if (Array.isArray(data.presets) && data.presets.length > 0) {
        selectPreset.innerHTML = '<option value="">⚡ Hazır Şablonlar (6 Endüstriyel)...</option>';
        state.loadedPresets = {};
        data.presets.forEach(p => {
          state.loadedPresets[p.preset_id] = p;
          selectPreset.innerHTML += `<option value="${p.preset_id}" title="${p.description || ''}">${p.name}</option>`;
        });
      }
    }
  } catch (err) {
    console.warn("Ön-ayarlar başlangıçta yüklenemedi:", err);
  }

  selectPreset.addEventListener("change", async (e) => {
    const presetId = e.target.value;
    if (!presetId) return;
    if (state.loadedPresets[presetId]) {
      applyConfigToForm(state.loadedPresets[presetId].config);
      return;
    }
    try {
      const res = await fetch("/api/presets");
      if (!res.ok) return;
      const data = await res.json();
      const match = data.presets.find(p => p.preset_id === presetId);
      if (match) {
        applyConfigToForm(match.config);
      }
    } catch (err) {
      console.error("Şablon yüklenirken hata:", err);
    }
  });
}

function initProjectManager() {
  const modal = document.getElementById("projectsModal");
  const openBtn = document.getElementById("btnOpenProjectsModal");
  const closeBtn = document.getElementById("closeProjectsModal");
  const saveBtn = document.getElementById("btnSaveCurrentProject");
  const exportBtn = document.getElementById("btnExportTrsim");
  const importBtn = document.getElementById("btnImportTrsim");
  const importFileInput = document.getElementById("inputImportTrsimFile");
  const nameInput = document.getElementById("inputProjectName");
  const container = document.getElementById("projectsListContainer");

  if (openBtn) {
    openBtn.addEventListener("click", () => {
      if (modal) modal.style.display = "flex";
      loadProjectsList();
    });
  }
  if (closeBtn) {
    closeBtn.addEventListener("click", () => {
      if (modal) modal.style.display = "none";
    });
  }

  // .trsim Dışa Aktar
  if (exportBtn) {
    exportBtn.addEventListener("click", () => {
      const projName = (nameInput?.value.trim()) || document.getElementById("projectTitle")?.textContent || "ThermalRunaway_Project";
      const trsimDoc = {
        format: "BatteryThermalRunawayWorkbench_TRSIM",
        version: "2.0.0",
        exported_at: new Date().toISOString(),
        name: projName,
        config: buildSimulationPayload()
      };
      const blob = new Blob([JSON.stringify(trsimDoc, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${projName.replace(/[^a-zA-Z0-9_-]/g, "_")}.trsim`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    });
  }

  // .trsim İçe Aktar
  if (importBtn && importFileInput) {
    importBtn.addEventListener("click", () => importFileInput.click());
    importFileInput.addEventListener("change", (e) => {
      const file = e.target.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = (evt) => {
        try {
          const parsed = JSON.parse(evt.target.result);
          const cfg = parsed.config || parsed.payload || parsed;
          applyConfigToForm(cfg);
          if (parsed.name && nameInput) nameInput.value = parsed.name;
          if (modal) modal.style.display = "none";
        } catch (err) {
          alert(".trsim dosyası okunamadı: " + err.message);
        } finally {
          importFileInput.value = "";
        }
      };
      reader.readAsText(file);
    });
  }

  async function loadProjectsList() {
    if (!container) return;
    container.innerHTML = '<div style="color:#94a3b8; font-size:11px; text-align:center; padding:12px;">Projeler yükleniyor...</div>';
    try {
      const res = await fetch("/api/projects");
      if (!res.ok) return;
      const data = await res.json();
      if (!data.projects || data.projects.length === 0) {
        container.innerHTML = '<div style="color:#64748b; font-size:11px; text-align:center; padding:16px;">Kayıtlı proje bulunmuyor. Yeni bir isim girerek kaydedebilirsiniz.</div>';
        return;
      }
      container.innerHTML = "";
      data.projects.forEach(p => {
        const row = document.createElement("div");
        row.className = "project-item-row";

        const payload = p.config_payload || p.payload || {};
        const meta = `${payload.rows || 3}x${payload.cols || 3} • ${payload.cell_format || '21700'} • ${payload.chemistry_id || ''}`;
        const dateStr = (p.created_at || p.updated_at || "").substring(0, 16);

        row.innerHTML = `
          <div>
            <div style="font-weight:700; color:#f8fafc; font-size:12px;">${p.name}</div>
            <div style="font-size:10px; color:#94a3b8; margin-top:2px;">${meta} — <span style="color:#64748b;">${dateStr}</span></div>
          </div>
          <div style="display:flex; gap:6px;">
            <button type="button" class="btn ghost-btn micro-btn" style="color:#38bdf8;" data-act="load" data-id="${p.project_id}">📂 Yükle</button>
            <button type="button" class="btn ghost-btn micro-btn" style="color:#ef4444;" data-act="del" data-id="${p.project_id}">🗑️ Sil</button>
          </div>
        `;

        row.querySelector('[data-act="load"]').addEventListener("click", () => {
          applyConfigToForm(payload);
          if (modal) modal.style.display = "none";
        });

        row.querySelector('[data-act="del"]').addEventListener("click", async () => {
          if (!confirm(`'${p.name}' projesini silmek istediğinize emin misiniz?`)) return;
          await fetch(`/api/projects/${p.project_id}`, { method: "DELETE" });
          loadProjectsList();
        });

        container.appendChild(row);
      });
    } catch (err) {
      container.innerHTML = `<div style="color:#ef4444; font-size:11px;">Hata: ${err.message}</div>`;
    }
  }

  if (saveBtn) {
    saveBtn.addEventListener("click", async () => {
      const name = nameInput.value.trim() || `Tasarım_${new Date().toISOString().substring(11, 19)}`;
      const payload = buildSimulationPayload();
      saveBtn.disabled = true;
      saveBtn.textContent = "Kaydediliyor...";
      try {
        const res = await fetch("/api/projects", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name, description: "Kullanıcı Kayıtlı Proje", payload })
        });
        if (res.ok) {
          nameInput.value = "";
          loadProjectsList();
        }
      } catch (err) {
        alert("Proje kaydedilemedi: " + err.message);
      } finally {
        saveBtn.disabled = false;
        saveBtn.textContent = "SQLite'a Kaydet";
      }
    });
  }
}

/* ================= 10. RUN A/B KARŞILAŞTIRMA YÖNETİCİSİ ================= */

function initCompareManager() {
  const modal = document.getElementById("compareModal");
  const openBtn = document.getElementById("btnOpenCompareModal");
  const closeBtn = document.getElementById("closeCompareModal");
  const selectA = document.getElementById("selectCompareJobA");
  const selectB = document.getElementById("selectCompareJobB");
  const execBtn = document.getElementById("btnExecuteCompare");
  const resultsArea = document.getElementById("compareResultsArea");
  const cardsArea = document.getElementById("compareDeltaCards");
  const chartCanvas = document.getElementById("compareChart");

  if (openBtn) {
    openBtn.addEventListener("click", async () => {
      if (modal) modal.style.display = "flex";
      try {
        const res = await fetch("/api/simulations");
        if (!res.ok) return;
        const data = await res.json();
        const sims = data.simulations || [];
        selectA.innerHTML = "";
        selectB.innerHTML = "";
        sims.forEach(s => {
          const optText = `${s.created_at ? s.created_at.substring(11, 19) : s.job_id.substring(0, 8)} | ${s.cell_count} Hücre | Tmax: ${s.max_temperature_C.toFixed(0)}°C`;
          selectA.innerHTML += `<option value="${s.job_id}">${optText}</option>`;
          selectB.innerHTML += `<option value="${s.job_id}">${optText}</option>`;
        });
        if (sims.length > 1) {
          selectB.selectedIndex = 1;
        }
      } catch (err) {
        console.error("Simülasyonlar listelenemedi:", err);
      }
    });
  }

  if (closeBtn) {
    closeBtn.addEventListener("click", () => {
      if (modal) modal.style.display = "none";
    });
  }

  if (execBtn) {
    execBtn.addEventListener("click", async () => {
      const jobA = selectA.value;
      const jobB = selectB.value;
      if (!jobA || !jobB) {
        alert("Lütfen karşılaştırmak için iki simülasyon seçin.");
        return;
      }
      execBtn.disabled = true;
      execBtn.textContent = "Karşılaştırılıyor...";
      try {
        const res = await fetch(`/api/simulations/compare?job_a=${jobA}&job_b=${jobB}`);
        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || "Karşılaştırma yapılamadı.");
        }
        const comp = await res.json();
        renderCompareResults(comp);
      } catch (err) {
        alert("Karşılaştırma hatası: " + err.message);
      } finally {
        execBtn.disabled = false;
        execBtn.textContent = "Kıyasla";
      }
    });
  }

  function renderCompareResults(comp) {
    resultsArea.style.display = "block";
    const dT = comp.delta_peak_temp_C || 0;
    const dH = comp.delta_affected_cells || 0;
    const dTime = comp.delta_first_propagation_s || 0;
    const dM = comp.delta_mass_kg || 0;

    const colorT = dT > 0 ? '#ef4444' : (dT < 0 ? '#10b981' : '#cbd5e1');
    const colorH = dH > 0 ? '#ef4444' : (dH < 0 ? '#10b981' : '#cbd5e1');
    const colorM = dM > 0 ? '#f59e0b' : (dM < 0 ? '#10b981' : '#cbd5e1');

    cardsArea.style.gridTemplateColumns = "repeat(4, 1fr)";
    cardsArea.innerHTML = `
      <div style="background:#0b0f17; border:1px solid #1e293b; border-radius:6px; padding:10px; text-align:center;">
        <span style="font-size:10px; color:#94a3b8; display:block;">PİK SICAKLIK FARKI</span>
        <strong style="font-size:15px; color:${colorT};">${dT > 0 ? '+' : ''}${dT.toFixed(1)} °C</strong>
        <span style="font-size:9px; color:#64748b; display:block; margin-top:2px;">A: ${comp.run_a.peak_temp_C.toFixed(0)}°C vs B: ${comp.run_b.peak_temp_C.toFixed(0)}°C</span>
      </div>
      <div style="background:#0b0f17; border:1px solid #1e293b; border-radius:6px; padding:10px; text-align:center;">
        <span style="font-size:10px; color:#94a3b8; display:block;">KAÇAK HÜCRE FARKI</span>
        <strong style="font-size:15px; color:${colorH};">${dH > 0 ? '+' : ''}${dH} Hücre</strong>
        <span style="font-size:9px; color:#64748b; display:block; margin-top:2px;">A: ${comp.run_a.affected_cells} vs B: ${comp.run_b.affected_cells}</span>
      </div>
      <div style="background:#0b0f17; border:1px solid #1e293b; border-radius:6px; padding:10px; text-align:center;">
        <span style="font-size:10px; color:#94a3b8; display:block;">İLK YAYILIM FARKI</span>
        <strong style="font-size:15px; color:#38bdf8;">${dTime > 0 ? '+' : ''}${dTime.toFixed(2)} s</strong>
        <span style="font-size:9px; color:#64748b; display:block; margin-top:2px;">Yayılım Gecikmesi</span>
      </div>
      <div style="background:#0b0f17; border:1px solid #1e293b; border-radius:6px; padding:10px; text-align:center;">
        <span style="font-size:10px; color:#94a3b8; display:block;">MODÜL KÜTLE FARKI</span>
        <strong style="font-size:15px; color:${colorM};">${dM > 0 ? '+' : ''}${dM.toFixed(2)} kg</strong>
        <span style="font-size:9px; color:#64748b; display:block; margin-top:2px;">A: ${(comp.run_a.module_mass_kg || 0).toFixed(2)}kg vs B: ${(comp.run_b.module_mass_kg || 0).toFixed(2)}kg</span>
      </div>
    `;

    if (state.compareChart) state.compareChart.destroy();
    const ctx = chartCanvas.getContext("2d");
    state.compareChart = new Chart(ctx, {
      type: "line",
      data: {
        labels: comp.time_points_s,
        datasets: [
          {
            label: `Run A: Tetikleyici Hücre (${comp.run_a.job_id.substring(0,6)})`,
            data: comp.run_a.trigger_temp_history,
            borderColor: "#38bdf8",
            borderWidth: 2,
            pointRadius: 0,
            fill: false
          },
          {
            label: `Run B: Tetikleyici Hücre (${comp.run_b.job_id.substring(0,6)})`,
            data: comp.run_b.trigger_temp_history,
            borderColor: "#f59e0b",
            borderWidth: 2,
            borderDash: [5, 4],
            pointRadius: 0,
            fill: false
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { labels: { color: "#cbd5e1", font: { size: 10 } } }
        },
        scales: {
          x: { title: { display: true, text: "Zaman (s)", color: "#94a3b8" }, ticks: { color: "#94a3b8" }, grid: { color: "#1e293b" } },
          y: { title: { display: true, text: "Sıcaklık (°C)", color: "#94a3b8" }, ticks: { color: "#94a3b8" }, grid: { color: "#1e293b" } }
        }
      }
    });
  }
}

/* ================= 11. OTOMATİK ARRHENIUS KALİBRASYON (AUTO-FIT) ================= */

function initAutoCalibrator() {
  const modal = document.getElementById("autoCalibrateModal");
  const openBtn = document.getElementById("btnOpenAutoCalibrateModal");
  const closeBtn = document.getElementById("closeAutoCalibrateModal");
  const demoBtn = document.getElementById("btnLoadDemoArcCsv");
  const runBtn = document.getElementById("btnRunAutoCalibrate");
  const applyBtn = document.getElementById("btnApplyCalibratedChem");
  const saveLibBtn = document.getElementById("btnSaveCalibratedChemToLib");
  const chemNameInput = document.getElementById("acChemName");
  const csvArea = document.getElementById("acCsvContent");
  const resultArea = document.getElementById("acResultArea");

  if (openBtn) openBtn.addEventListener("click", () => { if (modal) modal.style.display = "flex"; });
  if (closeBtn) closeBtn.addEventListener("click", () => { if (modal) modal.style.display = "none"; });

  if (demoBtn) {
    demoBtn.addEventListener("click", () => {
      csvArea.value = [
        "time_s,temperature_C",
        "0.0, 50.0",
        "300.0, 80.0",
        "600.0, 110.0",
        "900.0, 140.0",
        "1050.0, 160.0",
        "1120.0, 185.0",
        "1160.0, 220.0",
        "1185.0, 280.0",
        "1200.0, 420.0",
        "1210.0, 680.0",
        "1220.0, 750.0",
        "1250.0, 740.0"
      ].join("\n");
    });
  }

  async function executeCalibrationRequest(persistToLib = false) {
    const csv = csvArea.value.trim();
    if (!csv) {
      alert("Lütfen deneysel CSV verisi girin veya 'Örnek ARC CSV Doldur' butonuna tıklayın.");
      return null;
    }
    const mass = parseFloat(document.getElementById("acCellMass").value) || 0.048;
    const cp = parseFloat(document.getElementById("acCellCp").value) || 950;
    const ratio = parseFloat(document.getElementById("acActiveRatio").value) || 0.60;
    const cName = chemNameInput?.value.trim() || "ARC_Kalibre_Hücre";

    const res = await fetch("/api/validation/auto-calibrate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        cell_mass_kg: mass,
        cp_J_per_kg_K: cp,
        cell_cp_J_per_kg_K: cp,
        active_mass_ratio: ratio,
        chemistry_name: cName,
        persist_to_library: persistToLib,
        csv_content: csv
      })
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Kalibrasyon tamamlanamadı.");
    }
    return await res.json();
  }

  if (runBtn) {
    runBtn.addEventListener("click", async () => {
      runBtn.disabled = true;
      runBtn.innerHTML = "⏳ Kissinger + SciPy TRF Least-Squares Çözülüyor...";

      try {
        const data = await executeCalibrationRequest(false);
        if (!data) return;
        state.lastCalibratedChem = data;

        const aVal = Number(data.A_pre_exponential_per_s ?? data.frequency_factor_A);
        const eaKj = Number(data.Ea_kJ_per_mol ?? (data.activation_energy_J_per_mol / 1000.0));
        const dhJg = Number(data.delta_H_J_per_g ?? (data.reaction_enthalpy_J_per_kg / 1000.0));
        const r2 = Number(data.r_squared ?? data.r2_score);
        const expTimes = data.experimental_times || data.fitted_times_s || [];
        const expTemps = data.experimental_temperatures || data.experimental_temperatures_C || [];
        const fitTemps = data.fitted_temperatures || data.fitted_temperatures_C || [];

        resultArea.style.display = "block";
        document.getElementById("acR2Badge").textContent = `R² = ${r2.toFixed(4)}`;
        document.getElementById("acValA").textContent = aVal.toExponential(2) + " 1/s";
        document.getElementById("acValEa").textContent = eaKj.toFixed(1) + " kJ/mol";
        document.getElementById("acValDh").textContent = dhJg.toFixed(0) + " J/g";
        document.getElementById("acValRmse").textContent = Number(data.rmse_C).toFixed(2) + " °C";

        if (state.acFitChart) state.acFitChart.destroy();
        const ctx = document.getElementById("acFitChart").getContext("2d");
        state.acFitChart = new Chart(ctx, {
          type: "line",
          data: {
            labels: expTimes,
            datasets: [
              {
                label: "Deneysel ARC",
                data: expTemps,
                borderColor: "#06b6d4",
                pointRadius: 2,
                borderWidth: 1.5,
                fill: false
              },
              {
                label: "Kalibre Arrhenius Modeli",
                data: fitTemps,
                borderColor: "#34d399",
                borderDash: [4, 4],
                pointRadius: 0,
                borderWidth: 2,
                fill: false
              }
            ]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { labels: { color: "#cbd5e1", font: { size: 9 } } } },
            scales: {
              x: { ticks: { color: "#94a3b8", maxTicksLimit: 6 }, grid: { color: "#1e293b" } },
              y: { ticks: { color: "#94a3b8", maxTicksLimit: 5 }, grid: { color: "#1e293b" } }
            }
          }
        });
      } catch (err) {
        alert("Kalibrasyon hatası: " + err.message);
      } finally {
        runBtn.disabled = false;
        runBtn.innerHTML = "<span>🚀</span> En Küçük Kareler (Least-Squares) ile Modeli Otomatik Kalibre Et";
      }
    });
  }

  if (saveLibBtn) {
    saveLibBtn.addEventListener("click", async () => {
      if (!state.lastCalibratedChem) return;
      saveLibBtn.disabled = true;
      saveLibBtn.textContent = "Kaydediliyor...";
      try {
        const saved = await executeCalibrationRequest(true);
        if (saved && saved.registered_chemistry_id) {
          await loadLibraries();
          document.getElementById("selectChemistry").value = saved.registered_chemistry_id;
          updateChemistryDetails();
          saveLibBtn.textContent = "✓ Kütüphaneye Eklendi";
        }
      } catch (err) {
        alert("Kütüphaneye kayıt hatası: " + err.message);
        saveLibBtn.textContent = "📥 Kalıcı Kütüphaneye Kaydet";
      } finally {
        saveLibBtn.disabled = false;
      }
    });
  }

  if (applyBtn) {
    applyBtn.addEventListener("click", async () => {
      if (!state.lastCalibratedChem) return;
      const d = state.lastCalibratedChem;
      const aVal = Number(d.A_pre_exponential_per_s ?? d.frequency_factor_A);
      const eaJ = Number(d.Ea_J_per_mol ?? d.activation_energy_J_per_mol);
      const dhJg = Number(d.delta_H_J_per_g ?? (d.reaction_enthalpy_J_per_kg / 1000.0));
      const ratioVal = Number(d.active_mass_ratio ?? (parseFloat(document.getElementById("acActiveRatio")?.value) || 0.60));

      const chkAdv = document.getElementById("checkboxAdvPhysics");
      if (chkAdv) {
        chkAdv.checked = true;
        chkAdv.dispatchEvent(new Event("change"));
      }
      const kinSel = document.getElementById("selectKineticsModel");
      if (kinSel) {
        kinSel.value = "single_step";
        kinSel.dispatchEvent(new Event("change"));
      }
      const fA = document.getElementById("inputAdvA");
      const fEa = document.getElementById("inputAdvEa");
      const fdH = document.getElementById("inputAdvDeltaH");
      const fRatio = document.getElementById("inputAdvRatio");
      if (fA) fA.value = aVal.toExponential(4);
      if (fEa) fEa.value = eaJ.toFixed(0);
      if (fdH) fdH.value = dhJg.toFixed(1);
      if (fRatio) fRatio.value = ratioVal.toFixed(2);

      if (modal) modal.style.display = "none";
      switchTreePanel("adv_physics");
    });
  }
}

/* ================= 12. DOCKED ALT ANALİTİK ÇEKMECESİ (5-TAB DRAWER) ================= */

function initAnalyticsDrawer() {
  const drawer = document.getElementById("analyticsDrawer");
  const toggleBtn = document.getElementById("btnToggleDrawer");
  const tabs = document.querySelectorAll(".drawer-tab");

  if (toggleBtn) {
    toggleBtn.addEventListener("click", () => {
      state.drawerExpanded = !state.drawerExpanded;
      drawer.classList.toggle("expanded", state.drawerExpanded);
      toggleBtn.textContent = state.drawerExpanded ? "▼ Küçült" : "▲ Genişlet";
      if (state.drawerChart) {
        setTimeout(() => state.drawerChart.resize(), 200);
      }
    });
  }

  tabs.forEach(tab => {
    tab.addEventListener("click", () => {
      tabs.forEach(t => t.classList.remove("active"));
      tab.classList.add("active");
      state.drawerActiveTab = tab.dataset.chart;
      renderDrawerChart(state.drawerActiveTab);
    });
  });
}

// Chart.js Zaman Çizelgesi Senkronize Dikey İmleç Eklentisi
const drawerTimeCursorPlugin = {
  id: "drawerTimeCursorPlugin",
  afterDraw(chart) {
    if (!state.simulationData || !chart.scales?.x || !chart.chartArea) return;
    const step = state.currentStepIndex || 0;
    const xPos = chart.scales.x.getPixelForValue(step);
    const { top, bottom, left, right } = chart.chartArea;
    if (xPos < left || xPos > right) return;
    const c = chart.ctx;
    c.save();
    c.beginPath();
    c.moveTo(xPos, top);
    c.lineTo(xPos, bottom);
    c.lineWidth = 1.5;
    c.strokeStyle = "rgba(56, 189, 248, 0.85)";
    c.setLineDash([4, 3]);
    c.stroke();
    c.restore();
  }
};

function renderDrawerChart(activeTab) {
  if (!state.simulationData) return;
  const simRes = state.simulationData.simulation_result;
  const timePts = simRes.time_points_s;
  const triggerId = state.simulationData.request_config.trigger_cell_id;
  const selectedId = state.selectedCellId;

  const ctx = document.getElementById("drawerChart")?.getContext("2d");
  if (!ctx) return;
  if (state.drawerChart) state.drawerChart.destroy();

  let datasets = [];
  let yTitle = "Değer";
  let extraScales = {};

  const getCellSeries = (dictObj, cid) => {
    if (!dictObj) return null;
    return dictObj[cid] || dictObj[String(cid)] || null;
  };

  if (activeTab === "temp") {
    yTitle = "Sıcaklık (°C)";
    const { tOnset, tTrigger } = getChemistryThresholds();
    datasets.push({
      label: `T_onset (${Math.round(tOnset)}°C)`,
      data: new Array(timePts.length).fill(tOnset),
      borderColor: "#f59e0b",
      borderDash: [5, 4],
      borderWidth: 1.5,
      pointRadius: 0,
      fill: false
    });
    datasets.push({
      label: `T_trigger (${Math.round(tTrigger)}°C)`,
      data: new Array(timePts.length).fill(tTrigger),
      borderColor: "#ef4444",
      borderDash: [4, 4],
      borderWidth: 1.5,
      pointRadius: 0,
      fill: false
    });
    Object.keys(simRes.temperature_history_C).forEach(idStr => {
      const id = parseInt(idStr, 10);
      const isSel = (id === selectedId);
      const isTrig = (id === triggerId);
      const col = isTrig ? "#ef4444" : (isSel ? "#38bdf8" : `hsl(${(id * 47 + 200) % 360}, 70%, 55%)`);
      const shellSeries = getCellSeries(simRes.temperature_history_C, id);
      datasets.push({
        label: isTrig ? `Hücre #${id} Kovan (Tetik)` : (isSel ? `Hücre #${id} Kovan (Seçili)` : `Hücre #${id}`),
        data: shellSeries,
        borderColor: col,
        borderWidth: (isSel || isTrig) ? 2.4 : 1.0,
        pointRadius: 0,
        fill: false
      });

      // Core-Shell aktifse tetikleyici ve seçili hücre için T_core kesikli eğrisini ekle
      if ((isTrig || isSel) && simRes.core_temperature_history_C) {
        const coreSeries = getCellSeries(simRes.core_temperature_history_C, id);
        if (coreSeries && shellSeries) {
          const maxDiff = coreSeries.reduce((acc, v, idx) => Math.max(acc, Math.abs(v - shellSeries[idx])), 0);
          if (maxDiff > 0.25) {
            datasets.push({
              label: `Hücre #${id} Çekirdek (T_core)`,
              data: coreSeries,
              borderColor: isTrig ? "#fca5a5" : "#7dd3fc",
              borderDash: [3, 3],
              borderWidth: 1.8,
              pointRadius: 0,
              fill: false
            });
          }
        }
      }
    });
  } else if (activeTab === "rate") {
    yTitle = "Öz-Isınma Hızı dT/dt (°C/s)";
    datasets.push({
      label: "TR Eşik Hızı (1.0 °C/s)",
      data: new Array(timePts.length).fill(1.0),
      borderColor: "#ef4444",
      borderDash: [5, 3],
      borderWidth: 1.5,
      pointRadius: 0,
      fill: false
    });
    const targetIds = [triggerId];
    if (selectedId !== triggerId) targetIds.push(selectedId);
    targetIds.forEach(id => {
      const temps = getCellSeries(simRes.temperature_history_C, id);
      if (!temps) return;
      const rates = [];
      for (let i = 0; i < timePts.length; i++) {
        if (i === 0) rates.push((temps[1] - temps[0]) / Math.max(1e-4, timePts[1] - timePts[0]));
        else if (i === timePts.length - 1) rates.push((temps[i] - temps[i-1]) / Math.max(1e-4, timePts[i] - timePts[i-1]));
        else rates.push((temps[i+1] - temps[i-1]) / Math.max(1e-4, timePts[i+1] - timePts[i-1]));
      }
      datasets.push({
        label: `Hücre #${id} dT/dt (°C/s)`,
        data: rates,
        borderColor: id === triggerId ? "#ef4444" : "#38bdf8",
        borderWidth: 2,
        pointRadius: 0,
        fill: false
      });
    });
  } else if (activeTab === "flux") {
    const targetId = getCellSeries(simRes.temperature_history_C, selectedId) ? selectedId : triggerId;
    yTitle = `Hücre #${targetId} Isı Akısı (Watt)`;
    const fluxes = simRes.heat_flux_history_W;
    if (fluxes) {
      const fluxDefs = [
        { key: "q_chem", label: `Kimyasal Reaksiyon (Q_chem #${targetId})`, color: "#ef4444", width: 2.2 },
        { key: "q_abuse", label: `Abuse / Tetikleme (Q_abuse #${targetId})`, color: "#fb923c", width: 1.8 },
        { key: "q_cond", label: `Komşu İletim (Q_cond #${targetId})`, color: "#eab308", width: 1.7 },
        { key: "q_rad", label: `Işınım Transferi (Q_rad #${targetId})`, color: "#a855f7", width: 1.5 },
        { key: "q_vent", label: `Gaz Jet Konveksiyonu (Q_vent #${targetId})`, color: "#f43f5e", width: 1.6 },
        { key: "q_cool", label: `Soğutma & Konveksiyon (Q_cool #${targetId})`, color: "#06b6d4", width: 1.7 }
      ];
      fluxDefs.forEach(fd => {
        const series = getCellSeries(fluxes[fd.key], targetId);
        if (Array.isArray(series)) {
          datasets.push({
            label: fd.label,
            data: series,
            borderColor: fd.color,
            borderWidth: fd.width,
            pointRadius: 0,
            fill: false
          });
        }
      });
    }
  } else if (activeTab === "kinetics") {
    yTitle = "Dönüşüm Derecesi (α)";
    const subForSelected = getCellSeries(simRes.sub_alpha_history, selectedId);
    const subTargetId = subForSelected ? selectedId : triggerId;
    const subs = subForSelected || getCellSeries(simRes.sub_alpha_history, triggerId);
    if (subs && Object.keys(subs).length > 0) {
      const subColors = {
        sei: "#38bdf8",
        anode: "#f59e0b",
        separator: "#ec4899",
        cathode: "#ef4444",
        electrolyte: "#a855f7"
      };
      const subNamesTr = {
        sei: "1. SEI Bozunumu",
        anode: "2. Anot-Elektrolit",
        separator: "3. Separatör Erimesi (Endo)",
        cathode: "4. Katot Bozunumu"
      };
      Object.keys(subs).forEach(rxName => {
        const lowKey = rxName.toLowerCase();
        datasets.push({
          label: `Hücre #${subTargetId} • ${subNamesTr[lowKey] || rxName}`,
          data: subs[rxName],
          borderColor: subColors[lowKey] || "#cbd5e1",
          borderWidth: 2,
          pointRadius: 0,
          fill: false
        });
      });
    } else {
      datasets.push({
        label: `Hücre #${triggerId} (Tetikleyici) α`,
        data: getCellSeries(simRes.alpha_history, triggerId) || [],
        borderColor: "#ef4444",
        borderWidth: 2,
        pointRadius: 0,
        fill: false
      });
      if (selectedId !== triggerId) {
        datasets.push({
          label: `Hücre #${selectedId} (Seçili) α`,
          data: getCellSeries(simRes.alpha_history, selectedId) || [],
          borderColor: "#38bdf8",
          borderWidth: 2,
          pointRadius: 0,
          fill: false
        });
      }
    }
  } else if (activeTab === "gas") {
    yTitle = "Gaz Hacmi (L) & % LEL";
    const gh = simRes.gas_hazard_summary;
    if (gh && Array.isArray(gh.gas_volume_history_L)) {
      datasets.push({
        label: "Kümülatif Gaz Hacmi (STP Litre)",
        data: gh.gas_volume_history_L,
        borderColor: "#34d399",
        borderWidth: 2.2,
        pointRadius: 0,
        fill: false,
        yAxisID: "y"
      });
      const enc = gh.enclosure_analysis;
      if (enc && Array.isArray(enc.lel_ratio_history_percent)) {
        datasets.push({
          label: "Yanıcılık Oranı (% LEL)",
          data: enc.lel_ratio_history_percent,
          borderColor: "#f59e0b",
          borderDash: [4, 3],
          borderWidth: 1.8,
          pointRadius: 0,
          fill: false,
          yAxisID: "y"
        });
      }
      if (enc && Array.isArray(enc.overpressure_history_kpa)) {
        datasets.push({
          label: "Mahfaza Aşırı Basıncı ΔP (kPa)",
          data: enc.overpressure_history_kpa,
          borderColor: "#f43f5e",
          borderWidth: 2.0,
          pointRadius: 0,
          fill: false,
          yAxisID: "y1"
        });
        extraScales = {
          y1: {
            type: "linear",
            display: true,
            position: "right",
            title: { display: true, text: "İç Basınç ΔP (kPa)", color: "#f43f5e", font: { size: 9 } },
            ticks: { color: "#fda4af", font: { size: 9 } },
            grid: { drawOnChartArea: false }
          }
        };
      }
    }
  }

  state.drawerChart = new Chart(ctx, {
    type: "line",
    data: { labels: timePts.map(t => Number(t).toFixed(1)), datasets },
    plugins: [drawerTimeCursorPlugin],
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 0 },
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { display: true, position: "top", labels: { color: "#cbd5e1", boxWidth: 10, font: { size: 9 } } }
      },
      scales: {
        x: { title: { display: true, text: "Zaman (s)", color: "#8391a2", font: { size: 10 } }, ticks: { color: "#8391a2", maxTicksLimit: 10, font: { size: 9 } }, grid: { color: "#1e293b" } },
        y: { title: { display: true, text: yTitle, color: "#8391a2", font: { size: 10 } }, ticks: { color: "#8391a2", font: { size: 9 } }, grid: { color: "#1e293b" } },
        ...extraScales
      }
    }
  });
}
