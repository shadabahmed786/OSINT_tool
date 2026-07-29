document.addEventListener("DOMContentLoaded", () => {
  const targetInput = document.getElementById("target-input");
  const detectedBadge = document.getElementById("detected-badge");
  const selectorOverride = document.getElementById("selector-override");
  const investigateForm = document.getElementById("investigate-form");
  const submitBtn = document.getElementById("submit-btn");

  const statsBar = document.getElementById("stats-bar");
  const statTotal = document.getElementById("stat-total");
  const statHigh = document.getElementById("stat-high");
  const statMed = document.getElementById("stat-med");
  const statOverall = document.getElementById("stat-overall");

  const resultsSection = document.getElementById("results-section");
  const findingsContainer = document.getElementById("findings-container");
  const findingsCount = document.getElementById("findings-count");
  const logCount = document.getElementById("log-count");
  const evidenceTableBody = document.getElementById("evidence-table-body");
  const exportMdBtn = document.getElementById("export-md-btn");
  const historyList = document.getElementById("history-list");

  const pwdInput = document.getElementById("pwd-input");
  const pwdCheckBtn = document.getElementById("pwd-check-btn");
  const pwdResult = document.getElementById("pwd-result");

  let currentInvestigationId = null;
  let pollingInterval = null;
  let allFindings = [];
  let currentFilter = "ALL";

  // Auto-detect selector type in input field
  targetInput.addEventListener("input", () => {
    const val = targetInput.value.trim();
    if (!val) {
      detectedBadge.textContent = "AUTO DETECT";
      return;
    }
    if (val.includes("@") && val.includes(".")) {
      detectedBadge.textContent = "TYPE: EMAIL";
    } else if (val.startsWith("+") || (/^\d+$/.test(val.replace(/\D/g, "")) && val.replace(/\D/g, "").length >= 7)) {
      detectedBadge.textContent = "TYPE: PHONE";
    } else if (val.includes(" ")) {
      detectedBadge.textContent = "TYPE: NAME";
    } else {
      detectedBadge.textContent = "TYPE: USERNAME";
    }
  });

  // Submit Investigation
  investigateForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const target = targetInput.value.trim();
    if (!target) return;

    const selectorType = selectorOverride.value || null;

    submitBtn.disabled = true;
    submitBtn.innerHTML = `<span>RUNNING PIVOT...</span>`;

    try {
      const resp = await fetch("/api/investigate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target, selector_type: selectorType })
      });

      if (!resp.ok) throw new Error("Failed to start investigation");

      const data = await resp.json();
      currentInvestigationId = data.id;

      // Reset & show view
      resultsSection.style.display = "block";
      statsBar.style.display = "grid";
      exportMdBtn.href = `/api/export/${currentInvestigationId}`;

      startPolling(currentInvestigationId);
    } catch (err) {
      alert("Error: " + err.message);
      submitBtn.disabled = false;
      submitBtn.innerHTML = `<span>RUN PIVOT</span>`;
    }
  });

  // Poll for investigation status
  function startPolling(id) {
    if (pollingInterval) clearInterval(pollingInterval);

    pollingInterval = setInterval(async () => {
      try {
        const resp = await fetch(`/api/investigations/${id}`);
        if (!resp.ok) return;

        const data = await resp.json();
        renderInvestigationData(data);

        if (data.status === "completed" || data.status === "failed") {
          clearInterval(pollingInterval);
          submitBtn.disabled = false;
          submitBtn.innerHTML = `<span>RUN PIVOT</span>`;
          loadHistory();
          if (data.status === "failed") {
            alert("Investigation status: Failed. " + (data.summary || ""));
          }
        }
      } catch (err) {
        console.error("Polling error:", err);
      }
    }, 1500);
  }

  function renderInvestigationData(data) {
    allFindings = data.findings || [];
    const evidenceLog = data.evidence_log || [];

    // Stats
    const total = allFindings.length;
    const high = allFindings.filter(f => f.confidence_tier === "HIGH").length;
    const med = allFindings.filter(f => f.confidence_tier === "MEDIUM").length;

    statTotal.textContent = total;
    statHigh.textContent = high;
    statMed.textContent = med;

    if (high > 0) {
      statOverall.textContent = "HIGH";
      statOverall.className = "stat-value tier-tag tier-badge HIGH";
    } else if (med > 0) {
      statOverall.textContent = "MEDIUM";
      statOverall.className = "stat-value tier-tag tier-badge MEDIUM";
    } else {
      statOverall.textContent = total > 0 ? "LOW" : "NONE";
      statOverall.className = "stat-value tier-tag tier-badge LOW";
    }

    findingsCount.textContent = total;
    logCount.textContent = evidenceLog.length;

    // Render Findings Grid
    renderFindingsGrid();
    loadPendingSelectors();

    // Render Audit Table
    evidenceTableBody.innerHTML = evidenceLog.map(log => `
      <tr>
        <td><code>${log.timestamp}</code></td>
        <td><span class="selector-badge">${log.action || log.event_type || 'audit'}</span></td>
        <td>${log.detail || log.details || ''}</td>
      </tr>
    `).join("");
  }

  async function loadPendingSelectors() {
    if (!currentInvestigationId) return;
    try {
      const resp = await fetch(`/api/investigations/${currentInvestigationId}/pending-selectors`);
      if (!resp.ok) return;
      const pendings = await resp.json();

      const pendingCount = document.getElementById("pending-count");
      const pendingList = document.getElementById("pending-list");
      if (pendingCount) pendingCount.textContent = pendings.length;

      if (!pendingList) return;

      if (pendings.length === 0) {
        pendingList.innerHTML = `<div style="grid-column: 1/-1; text-align: center; color: var(--text-muted); padding: 20px;">No pending secondary selectors awaiting approval.</div>`;
        return;
      }

      pendingList.innerHTML = pendings.map(p => `
        <div class="finding-card">
          <div class="finding-header">
            <span class="platform-name">${p.selector_value}</span>
            <span class="selector-badge">${p.selector_type.toUpperCase()}</span>
          </div>
          <div class="finding-body">
            <div style="font-size: 12px; color: var(--text-muted);">Discovered secondary target. Approval required to pivot enumeration (§0).</div>
          </div>
          <div class="finding-footer">
            <button class="btn-primary" style="padding: 4px 10px; font-size: 12px;" onclick="approvePivot(${p.id})">Approve Pivot</button>
          </div>
        </div>
      `).join("");
    } catch (err) {
      console.error("Pending selector fetch error:", err);
    }
  }

  window.approvePivot = async function(selectorId) {
    if (!currentInvestigationId) return;
    try {
      const resp = await fetch(`/api/investigations/${currentInvestigationId}/approve-selector/${selectorId}`, { method: "POST" });
      if (resp.ok) {
        loadPendingSelectors();
        submitBtn.disabled = true;
        submitBtn.innerHTML = `<span>RUNNING PIVOT...</span>`;
        startPolling(currentInvestigationId);
      } else {
        alert("Error approving pivot target: Server returned error");
      }
    } catch (err) {
      alert("Error approving pivot: " + err.message);
    }
  };

  function renderFindingsGrid() {
    let filtered = allFindings;
    if (currentFilter !== "ALL") {
      filtered = allFindings.filter(f => f.confidence_tier === currentFilter);
    }

    if (filtered.length === 0) {
      findingsContainer.innerHTML = `<div class="card" style="grid-column: 1/-1; text-align: center; color: var(--text-muted);">No findings discovered matching filter.</div>`;
      return;
    }

    findingsContainer.innerHTML = filtered.map(f => `
      <div class="finding-card">
        <div class="finding-header">
          <span class="platform-name">${f.platform}</span>
          <span class="tier-badge ${f.confidence_tier}">${f.confidence_tier} (${f.confidence_score}%)</span>
        </div>
        <div class="finding-body">
          <div class="finding-user">@${f.display_name || f.matched_selector}</div>
          <div class="finding-bio">${f.bio || "Account discovered during pivot check."}</div>
        </div>
        <div class="finding-footer">
          <span>Source: ${f.matched_selector}</span>
          ${f.profile_url ? `<a href="${f.profile_url}" target="_blank" class="profile-link">View Profile &rarr;</a>` : ""}
        </div>
      </div>
    `).join("");
  }

  // Filter Buttons
  document.querySelectorAll(".filter-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".filter-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      currentFilter = btn.dataset.filter;
      renderFindingsGrid();
    });
  });

  // Tabs Switcher
  document.querySelectorAll(".tab-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));

      btn.classList.add("active");
      document.getElementById(btn.dataset.tab).classList.add("active");
    });
  });

  // Password Exposure Tool
  pwdCheckBtn.addEventListener("click", async () => {
    const val = pwdInput.value.trim();
    if (!val) return;

    pwdResult.style.display = "block";
    pwdResult.className = "pwd-result-box";
    pwdResult.textContent = "Checking HIBP k-Anonymity Hash DB...";

    try {
      const resp = await fetch("/api/check-password-hash", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password: val })
      });
      const data = await resp.json();

      if (data.exposed) {
        pwdResult.className = "pwd-result-box danger";
        pwdResult.textContent = `⚠️ BREACH DETECTED: Password hash SHA-1 (${data.prefix}...) was found ${data.count.toLocaleString()} times in known breaches!`;
      } else {
        pwdResult.className = "pwd-result-box safe";
        pwdResult.textContent = `✅ CLEAN: Password hash was not found in the HIBP dataset.`;
      }
    } catch (err) {
      pwdResult.className = "pwd-result-box danger";
      pwdResult.textContent = "Error: " + err.message;
    }
  });

  // History loader
  async function loadHistory() {
    try {
      const resp = await fetch("/api/investigations");
      if (!resp.ok) return;
      const list = await resp.json();

      if (list.length === 0) return;

      historyList.innerHTML = list.slice(0, 5).map(item => {
        const target = item.target || item.initial_selector || "Unknown";
        const selectorType = (item.selector_type || item.initial_selector_type || "N/A").toUpperCase();
        return `
        <div class="history-item" onclick="viewHistory('${item.id}')">
          <div>
            <strong>${target}</strong> <span class="selector-badge">${selectorType}</span>
          </div>
          <div><code>${item.created_at || ''}</code></div>
        </div>
      `;
      }).join("");
    } catch (err) {
      console.error("History load error:", err);
    }
  }

    window.viewHistory = function(id) {
    currentInvestigationId = id;
    resultsSection.style.display = "block";
    statsBar.style.display = "grid";
    exportMdBtn.href = `/api/export/${id}`;
    startPolling(id);
  };

  // AI Executive Report Handler
  const aiSummaryBtn = document.getElementById("ai-summary-btn");
  const aiSummaryCard = document.getElementById("ai-summary-card");
  const aiSummaryContent = document.getElementById("ai-summary-content");
  const aiEngineBadge = document.getElementById("ai-engine-badge");

  if (aiSummaryBtn) {
    aiSummaryBtn.addEventListener("click", async () => {
      if (!currentInvestigationId) return;

      aiSummaryCard.style.display = "block";
      aiSummaryContent.textContent = "⚡ Running local AI inference & intelligence synthesis...";

      try {
        const resp = await fetch(`/api/investigations/${currentInvestigationId}/ai-summary`, { method: "POST" });
        if (!resp.ok) throw new Error("Failed to generate summary");
        const data = await resp.json();

        aiEngineBadge.textContent = data.engine;
        aiSummaryContent.textContent = data.summary;
      } catch (err) {
        aiSummaryContent.textContent = "Error generating AI summary: " + err.message;
      }
    });
  }

  // Canvas Link Analysis Node Graph Visualizer
  const canvas = document.getElementById("graph-canvas");
  let nodes = [];
  let animFrameId = null;

  function renderNodeGraph() {
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const dpr = window.devicePixelRatio || 1;

    // Auto resize canvas
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);

    const width = rect.width;
    const height = rect.height;
    const centerX = width / 2;
    const centerY = height / 2;

    // Build Node objects from findings
    nodes = [];

    // Target center node
    const targetVal = targetInput.value.trim() || "TARGET";
    nodes.push({
      id: "center",
      label: targetVal,
      type: "target",
      x: centerX,
      y: centerY,
      radius: 28,
      color: "#38bdf8",
      url: null
    });

    if (allFindings.length > 0) {
      const radiusStep = Math.min(width, height) * 0.35;
      const angleStep = (2 * Math.PI) / allFindings.length;

      allFindings.forEach((f, idx) => {
        const angle = idx * angleStep;
        const nx = centerX + radiusStep * Math.cos(angle);
        const ny = centerY + radiusStep * Math.sin(angle);

        let color = "#64748b"; // Low
        if (f.confidence_tier === "HIGH") color = "#10b981";
        else if (f.confidence_tier === "MEDIUM") color = "#f59e0b";

        nodes.push({
          id: `node-${idx}`,
          label: f.platform,
          subLabel: `@${f.display_name || f.matched_selector}`,
          type: "finding",
          x: nx,
          y: ny,
          radius: 18,
          color: color,
          url: f.profile_url,
          tier: f.confidence_tier,
          score: f.confidence_score
        });
      });
    }

    let pulseAngle = 0;

    function draw() {
      ctx.clearRect(0, 0, width, height);
      pulseAngle += 0.03;

      // Draw connecting edges
      const centerNode = nodes[0];
      for (let i = 1; i < nodes.length; i++) {
        const n = nodes[i];
        ctx.beginPath();
        ctx.moveTo(centerNode.x, centerNode.y);
        ctx.lineTo(n.x, n.y);
        ctx.strokeStyle = n.color;
        ctx.globalAlpha = 0.35;
        ctx.lineWidth = n.tier === "HIGH" ? 2.5 : 1.5;
        ctx.stroke();
        ctx.globalAlpha = 1.0;
      }

      // Draw Nodes
      nodes.forEach((n, idx) => {
        if (n.type === "target") {
          // Outer pulsing ring for center target
          const pulseR = n.radius + Math.sin(pulseAngle) * 6;
          ctx.beginPath();
          ctx.arc(n.x, n.y, pulseR, 0, Math.PI * 2);
          ctx.strokeStyle = "rgba(56, 189, 248, 0.4)";
          ctx.lineWidth = 3;
          ctx.stroke();

          // Center solid fill
          ctx.beginPath();
          ctx.arc(n.x, n.y, n.radius, 0, Math.PI * 2);
          ctx.fillStyle = n.color;
          ctx.fill();

          ctx.fillStyle = "#0f172a";
          ctx.font = "bold 12px Inter, sans-serif";
          ctx.textAlign = "center";
          ctx.textBaseline = "middle";
          ctx.fillText(n.label.slice(0, 10), n.x, n.y);
        } else {
          // Finding Node
          ctx.beginPath();
          ctx.arc(n.x, n.y, n.radius, 0, Math.PI * 2);
          ctx.fillStyle = n.color;
          ctx.shadowColor = n.color;
          ctx.shadowBlur = 10;
          ctx.fill();
          ctx.shadowBlur = 0;

          ctx.fillStyle = "#f8fafc";
          ctx.font = "bold 11px Inter, sans-serif";
          ctx.textAlign = "center";
          ctx.fillText(n.label, n.x, n.y + n.radius + 14);

          ctx.fillStyle = "#94a3b8";
          ctx.font = "10px JetBrains Mono, monospace";
          ctx.fillText(n.subLabel.slice(0, 14), n.x, n.y + n.radius + 26);
        }
      });

      animFrameId = requestAnimationFrame(draw);
    }

    if (animFrameId) cancelAnimationFrame(animFrameId);
    draw();
  }

  // Handle canvas click to open profile URL
  if (canvas) {
    canvas.addEventListener("click", (e) => {
      const rect = canvas.getBoundingClientRect();
      const clickX = e.clientX - rect.left;
      const clickY = e.clientY - rect.top;

      for (let i = 1; i < nodes.length; i++) {
        const n = nodes[i];
        const dist = Math.hypot(clickX - n.x, clickY - n.y);
        if (dist <= n.radius + 5 && n.url) {
          window.open(n.url, "_blank");
          break;
        }
      }
    });
  }

  // Re-render graph on tab change or data update
  const origRender = renderInvestigationData;
  renderInvestigationData = function(data) {
    origRender(data);
    renderNodeGraph();
  };

  document.querySelectorAll(".tab-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      if (btn.dataset.tab === "graph-tab") {
        setTimeout(renderNodeGraph, 100);
      }
    });
  });

  loadHistory();
});
