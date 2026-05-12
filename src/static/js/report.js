document.addEventListener("DOMContentLoaded", function () {
  const body = document.body;
  const cards = Array.from(document.querySelectorAll(".module-card"));
  const searchInput = document.getElementById("searchInput");
  const problemsOnly = document.getElementById("problemsOnly");
  const filterButtons = Array.from(document.querySelectorAll(".status-filter-btn"));
  const categorySections = Array.from(document.querySelectorAll(".category-section"));
  const checklistSection = document.getElementById("admin-checklist");
  const diagnosisSection = document.getElementById("diagnosis-section");
  const moduleDetails = Array.from(document.querySelectorAll(".module-details"));
  const toggleAllCardsButton = document.getElementById("toggleAllCards");
  const stickyHero = document.querySelector(".sticky-hero");
  const toggleHeroPanelButton = document.getElementById("toggleHeroPanel");
  const runlogModuleCheckboxes = Array.from(document.querySelectorAll(".runlog-module-checkbox"));
  const resetRunlogSelectionButton = document.getElementById("resetRunlogSelection");
  const runlogSelectionCount = document.getElementById("runlogSelectionCount");


  let activeStatusFilter = "all";

  function normalize(value) {
    return String(value || "").toLowerCase().trim();
  }

  function matchesProblemsOnly(status) {
    return ["warning", "critical", "error"].includes(status);
  }

  function getSelectedRunlogModuleIds() {
    return new Set(
      runlogModuleCheckboxes
        .filter((checkbox) => checkbox.checked)
        .map((checkbox) => String(checkbox.dataset.moduleId || "").trim())
        .filter(Boolean)
    );
  }

  function updateRunlogSelectionUi() {
    const selectedIds = getSelectedRunlogModuleIds();
    if (runlogSelectionCount) {
      const label = runlogSelectionCount.dataset.label || runlogSelectionCount.textContent.split(":")[0] || "Ausgewählt";
      runlogSelectionCount.textContent = `${label}: ${selectedIds.size}`;
    }

    document.querySelectorAll(".run-log-table tbody tr[data-module-id]").forEach((row) => {
      const rowModuleId = String(row.dataset.moduleId || "").trim();
      row.classList.toggle("is-selected", selectedIds.has(rowModuleId));
    });
  }

  function applyFilters() {
    const searchTerm = normalize(searchInput ? searchInput.value : "");
    const onlyProblems = Boolean(problemsOnly && problemsOnly.checked);
    const selectedModuleIds = getSelectedRunlogModuleIds();
    const hasRunlogSelection = selectedModuleIds.size > 0;

    cards.forEach((card) => {
      const status = normalize(card.dataset.status);
      const searchBlob = normalize(card.dataset.search);
      const moduleId = String(card.dataset.moduleId || "").trim();
      const matchesSearch = !searchTerm || searchBlob.includes(searchTerm);
      const matchesStatus = activeStatusFilter === "all" || status === activeStatusFilter;
      const matchesProblemToggle = !onlyProblems || matchesProblemsOnly(status);
      const matchesRunlogSelection = !hasRunlogSelection || selectedModuleIds.has(moduleId);
      const visible = matchesSearch && matchesStatus && matchesProblemToggle && matchesRunlogSelection;
      card.classList.toggle("is-hidden-by-filter", !visible);
    });

    categorySections.forEach((section) => {
      const visibleCards = section.querySelectorAll(".module-card:not(.is-hidden-by-filter)");
      section.classList.toggle("is-hidden-by-filter", visibleCards.length === 0);
    });

    updateRunlogSelectionUi();
  }

  filterButtons.forEach((button) => {
    button.addEventListener("click", function () {
      activeStatusFilter = normalize(button.dataset.statusFilter || "all");
      filterButtons.forEach((btn) => btn.classList.toggle("is-active", btn === button));
      applyFilters();
    });
  });

  if (searchInput) {
    searchInput.addEventListener("input", applyFilters);
  }

  if (problemsOnly) {
    problemsOnly.addEventListener("change", applyFilters);
  }

  runlogModuleCheckboxes.forEach((checkbox) => {
    checkbox.addEventListener("change", function () {
      activeStatusFilter = "all";
      filterButtons.forEach((btn) => {
        btn.classList.toggle("is-active", normalize(btn.dataset.statusFilter || "all") === "all");
      });
      applyFilters();
    });
  });

  if (resetRunlogSelectionButton) {
    resetRunlogSelectionButton.addEventListener("click", function () {
      runlogModuleCheckboxes.forEach((checkbox) => {
        checkbox.checked = false;
      });
      applyFilters();
    });
  }

  function areAllModuleCardsOpen() {
    return moduleDetails.length > 0 && moduleDetails.every((detail) => detail.open);
  }

  function updateToggleAllCardsButton() {
    if (!toggleAllCardsButton) return;
    const expandLabel = toggleAllCardsButton.dataset.labelExpand || "Expand all cards";
    const collapseLabel = toggleAllCardsButton.dataset.labelCollapse || "Collapse all cards";
    const allOpen = areAllModuleCardsOpen();
    toggleAllCardsButton.textContent = allOpen ? collapseLabel : expandLabel;
    toggleAllCardsButton.setAttribute("aria-expanded", allOpen ? "true" : "false");
  }

  if (toggleAllCardsButton) {
    toggleAllCardsButton.addEventListener("click", function () {
      const shouldOpen = !areAllModuleCardsOpen();
      moduleDetails.forEach((detail) => {
        detail.open = shouldOpen;
      });
      updateToggleAllCardsButton();
    });
  }

  function setHeroCollapsed(collapsed) {
    if (!stickyHero || !toggleHeroPanelButton) return;
    stickyHero.classList.toggle("is-collapsed", collapsed);
    const labelExpanded = toggleHeroPanelButton.dataset.labelExpanded || "Übersicht einklappen";
    const labelCollapsed = toggleHeroPanelButton.dataset.labelCollapsed || "Übersicht ausklappen";
    const label = toggleHeroPanelButton.querySelector(".hero-collapse-btn-text");
    if (label) {
      label.textContent = collapsed ? labelCollapsed : labelExpanded;
    }
    toggleHeroPanelButton.setAttribute("aria-expanded", collapsed ? "false" : "true");
  }

  if (toggleHeroPanelButton) {
    toggleHeroPanelButton.addEventListener("click", function () {
      const collapsed = Boolean(stickyHero && stickyHero.classList.contains("is-collapsed"));
      setHeroCollapsed(!collapsed);
    });
  }

  moduleDetails.forEach((detail) => {
    detail.addEventListener("toggle", updateToggleAllCardsButton);
  });

  const sidepanel = document.getElementById("sidepanel");
  const sidepanelBackdrop = document.getElementById("sidepanelBackdrop");
  const openSidePanel = document.getElementById("openSidePanel");
  const closeSidePanel = document.getElementById("closeSidePanel");
  const sidepanelTabWrap = document.getElementById("sidepanelTabWrap");

  function setSidepanelOpen(open) {
    if (!sidepanel) return;
    sidepanel.classList.toggle("open", open);
    if (sidepanelBackdrop) sidepanelBackdrop.classList.toggle("open", open);
    if (sidepanelTabWrap) sidepanelTabWrap.classList.toggle("is-open", open);
    sidepanel.setAttribute("aria-hidden", open ? "false" : "true");
    if (openSidePanel) openSidePanel.setAttribute("aria-expanded", open ? "true" : "false");
    body.classList.toggle("sidepanel-open", open);
  }

  if (openSidePanel) {
    openSidePanel.addEventListener("click", () => {
      setDiagnosisOpen(false);
      setChecklistOpen(false);
      setSidepanelOpen(true);
    });
  }
  if (closeSidePanel) closeSidePanel.addEventListener("click", () => setSidepanelOpen(false));
  if (sidepanelBackdrop) sidepanelBackdrop.addEventListener("click", () => setSidepanelOpen(false));

  const openDiagnosisTab = document.getElementById("openDiagnosisTab");
  const closeDiagnosisPanel = document.getElementById("closeDiagnosisPanel");
  const diagnosisTabWrap = document.getElementById("diagnosisTabWrap");
  const diagnosisNavLinks = Array.from(document.querySelectorAll('a[href="#diagnosis-section"]'));
  const openChecklistTab = document.getElementById("openChecklistTab");
  const closeChecklistPanel = document.getElementById("closeChecklistPanel");
  const checklistTabWrap = document.getElementById("checklistTabWrap");
  const expandChecklist = document.getElementById("expandChecklist");
  const resetChecklist = document.getElementById("resetChecklist");
  const checklistBoxes = Array.from(document.querySelectorAll("[data-checklist-group]"));
  const checklistStorageKey = "systemdiagreport_checklist_state_v1";

  if (checklistSection) {
    checklistSection.classList.add("checklist-drawer");
  }

  if (diagnosisSection) {
    diagnosisSection.classList.add("diagnosis-drawer");
  }

  function setDiagnosisOpen(open) {
    if (!diagnosisSection) return;
    diagnosisSection.classList.toggle("open", open);
    if (diagnosisTabWrap) diagnosisTabWrap.classList.toggle("is-open", open);
    if (openDiagnosisTab) openDiagnosisTab.setAttribute("aria-expanded", open ? "true" : "false");
    body.classList.toggle("diagnosis-open", open);
  }

  function setChecklistOpen(open) {
    if (!checklistSection) return;
    checklistSection.classList.toggle("open", open);
    if (checklistTabWrap) checklistTabWrap.classList.toggle("is-open", open);
    if (openChecklistTab) openChecklistTab.setAttribute("aria-expanded", open ? "true" : "false");
    body.classList.toggle("checklist-open", open);
  }

  if (openDiagnosisTab) {
    openDiagnosisTab.addEventListener("click", () => {
      setSidepanelOpen(false);
      setChecklistOpen(false);
      setDiagnosisOpen(true);
    });
  }
  if (closeDiagnosisPanel) closeDiagnosisPanel.addEventListener("click", () => setDiagnosisOpen(false));
  diagnosisNavLinks.forEach((link) => {
    link.addEventListener("click", function (event) {
      event.preventDefault();
      setSidepanelOpen(false);
      setChecklistOpen(false);
      setDiagnosisOpen(true);
    });
  });

  if (openChecklistTab) {
    openChecklistTab.addEventListener("click", () => {
      setSidepanelOpen(false);
      setDiagnosisOpen(false);
      setChecklistOpen(true);
    });
  }
  if (closeChecklistPanel) closeChecklistPanel.addEventListener("click", () => setChecklistOpen(false));

  function saveChecklistState() {
    if (!checklistBoxes.length) return;
    const state = {};
    checklistBoxes.forEach((box, index) => {
      state[index] = Boolean(box.checked);
    });
    try {
      localStorage.setItem(checklistStorageKey, JSON.stringify(state));
    } catch (error) {
      console.warn("Checklist state could not be saved.", error);
    }
  }

  function loadChecklistState() {
    if (!checklistBoxes.length) return;
    try {
      const raw = localStorage.getItem(checklistStorageKey);
      if (!raw) return;
      const state = JSON.parse(raw);
      checklistBoxes.forEach((box, index) => {
        box.checked = Boolean(state[index]);
      });
    } catch (error) {
      console.warn("Checklist state could not be loaded.", error);
    }
  }

  function updateChecklistCounts() {
    const groupMap = new Map();
    checklistBoxes.forEach((box) => {
      const group = box.dataset.checklistGroup || "default";
      if (!groupMap.has(group)) {
        groupMap.set(group, []);
      }
      groupMap.get(group).push(box);
    });

    document.querySelectorAll(".checklist-count").forEach((badge) => {
      const group = badge.dataset.group || "default";
      const boxes = groupMap.get(group) || [];
      const checked = boxes.filter((box) => box.checked).length;
      const total = boxes.length;
      badge.textContent = `${checked}/${total}`;
      badge.classList.toggle("is-partial", checked > 0 && checked < total);
      badge.classList.toggle("is-complete", total > 0 && checked === total);

      const details = badge.closest(".checklist-group");
      if (details) {
        details.classList.toggle("has-progress", checked > 0);
        details.classList.toggle("is-complete", total > 0 && checked === total);
      }
    });
  }

  checklistBoxes.forEach((box) => {
    box.addEventListener("change", function () {
      saveChecklistState();
      updateChecklistCounts();
    });
  });

  if (expandChecklist) {
    expandChecklist.addEventListener("click", function () {
      document.querySelectorAll(".checklist-group").forEach((group) => {
        group.open = true;
      });
    });
  }

  if (resetChecklist) {
    resetChecklist.addEventListener("click", function () {
      checklistBoxes.forEach((box) => {
        box.checked = false;
      });
      try {
        localStorage.removeItem(checklistStorageKey);
      } catch (error) {
        console.warn("Checklist state could not be cleared.", error);
      }
      updateChecklistCounts();
    });
  }

  loadChecklistState();
  updateChecklistCounts();
  updateToggleAllCardsButton();
  if (runlogSelectionCount) {
    runlogSelectionCount.dataset.label = runlogSelectionCount.textContent.split(":")[0] || runlogSelectionCount.textContent;
  }
  applyFilters();

  if (diagnosisSection && String(diagnosisSection.dataset.hasCases || "").toLowerCase() === "true") {
    setDiagnosisOpen(true);
  }


  document.querySelectorAll(".ai-copy-btn").forEach((button) => {
    button.addEventListener("click", async function () {
      const textToCopy = button.dataset.copyText || "";
      if (!textToCopy) return;
      try {
        await navigator.clipboard.writeText(textToCopy);
        const originalText = button.textContent;
        const copiedLabel = button.dataset.copiedLabel || "Prompt copied";
        button.textContent = copiedLabel;
        window.setTimeout(() => {
          button.textContent = originalText;
        }, 1800);
      } catch (error) {
        console.warn("Clipboard copy failed.", error);
      }
    });
  });

  const generatedActions = document.querySelectorAll(".generated-action");
  if (!diagnosisSection && checklistSection && generatedActions.length) {
    setChecklistOpen(true);
  }
});
