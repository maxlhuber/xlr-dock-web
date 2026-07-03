const state = {
  config: null,
  pending: new Map(),
  debounce: new Map(),
};

const $ = (id) => document.getElementById(id);

const ui = {
  connectionState: $("connectionState"),
  connectionText: $("connectionText"),
  deviceName: $("deviceName"),
  firmwareVersion: $("firmwareVersion"),
  windex: $("windex"),
  meterLeft: $("meterLeft"),
  meterRight: $("meterRight"),
  mixValue: $("mixValue"),
  mixSlider: $("mixSlider"),
  gainValue: $("gainValue"),
  gainSlider: $("gainSlider"),
  headphoneValue: $("headphoneValue"),
  headphoneSlider: $("headphoneSlider"),
  muteButton: $("muteButton"),
  lowZButton: $("lowZButton"),
  clipguardButton: $("clipguardButton"),
};

function setConnection(online, text) {
  ui.connectionState.classList.toggle("online", online);
  ui.connectionState.classList.toggle("offline", !online);
  ui.connectionText.textContent = text;
}

function fmtDb(value) {
  return `${Number(value).toFixed(1)} dB`;
}

function renderStatus(data) {
  state.config = data.config;
  setConnection(true, "Online");
  ui.deviceName.textContent = data.device?.name || "-";
  ui.windex.textContent = data.device?.windex || "-";
  ui.firmwareVersion.textContent = data.device_info?.firmware_version || "-";

  const config = data.config;
  ui.mixSlider.value = config.monitor_mix;
  ui.mixValue.textContent = `${config.monitor_mix}% Mic`;
  ui.gainSlider.value = config.gain_db;
  ui.gainValue.textContent = fmtDb(config.gain_db);
  ui.headphoneSlider.value = config.headphone_volume_db;
  ui.headphoneValue.textContent = fmtDb(config.headphone_volume_db);
  ui.muteButton.classList.toggle("active", Boolean(config.muted));
  ui.lowZButton.classList.toggle("active", Boolean(config.low_impedance));
  ui.clipguardButton.classList.toggle("active", Boolean(config.clipguard));
}

async function request(path, options = {}) {
  const response = await fetch(path, {
    cache: "no-store",
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await response.json();
  if (!response.ok || !data.ok) {
    throw new Error(data.error || `HTTP ${response.status}`);
  }
  return data;
}

async function refreshStatus() {
  try {
    const data = await request("/api/status");
    renderStatus(data);
  } catch (error) {
    setConnection(false, "Offline");
    ui.deviceName.textContent = error.message;
  }
}

function meterPercent(value) {
  if (!Number.isFinite(value) || value <= 0) {
    return 0;
  }
  const db = 20 * Math.log10(value / 0xffffffff);
  return Math.max(0, Math.min(100, 100 + db * 2.4));
}

async function refreshMeters() {
  try {
    const data = await request("/api/meters");
    ui.meterLeft.style.width = `${meterPercent(data.left)}%`;
    ui.meterRight.style.width = `${meterPercent(data.right)}%`;
  } catch (_error) {
    ui.meterLeft.style.width = "0";
    ui.meterRight.style.width = "0";
  }
}

function updateConfig(key, value, immediate = false) {
  state.pending.set(key, value);
  window.clearTimeout(state.debounce.get(key));
  const run = async () => {
    const payload = Object.fromEntries(state.pending);
    state.pending.clear();
    try {
      const data = await request("/api/config", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      renderStatus({ ...data, device_info: undefined });
    } catch (error) {
      setConnection(false, "Fehler");
      ui.deviceName.textContent = error.message;
      refreshStatus();
    }
  };
  if (immediate) {
    run();
    return;
  }
  state.debounce.set(key, window.setTimeout(run, 140));
}

ui.mixSlider.addEventListener("input", () => {
  ui.mixValue.textContent = `${ui.mixSlider.value}% Mic`;
  updateConfig("monitor_mix", Number(ui.mixSlider.value));
});

ui.gainSlider.addEventListener("input", () => {
  ui.gainValue.textContent = fmtDb(ui.gainSlider.value);
  updateConfig("gain_db", Number(ui.gainSlider.value));
});

ui.headphoneSlider.addEventListener("input", () => {
  ui.headphoneValue.textContent = fmtDb(ui.headphoneSlider.value);
  updateConfig("headphone_volume_db", Number(ui.headphoneSlider.value));
});

document.querySelectorAll("[data-mix]").forEach((button) => {
  button.addEventListener("click", () => {
    const value = Number(button.dataset.mix);
    ui.mixSlider.value = value;
    ui.mixValue.textContent = `${value}% Mic`;
    updateConfig("monitor_mix", value, true);
  });
});

ui.muteButton.addEventListener("click", async () => {
  try {
    const data = await request("/api/actions/toggle-mute", { method: "POST", body: "{}" });
    renderStatus({ ...data, device: { name: ui.deviceName.textContent, windex: ui.windex.textContent } });
  } catch (error) {
    setConnection(false, "Fehler");
    ui.deviceName.textContent = error.message;
  }
});

ui.lowZButton.addEventListener("click", () => {
  const next = !ui.lowZButton.classList.contains("active");
  ui.lowZButton.classList.toggle("active", next);
  updateConfig("low_impedance", next, true);
});

ui.clipguardButton.addEventListener("click", () => {
  const next = !ui.clipguardButton.classList.contains("active");
  ui.clipguardButton.classList.toggle("active", next);
  updateConfig("clipguard", next, true);
});

refreshStatus();
refreshMeters();
window.setInterval(refreshStatus, 3500);
window.setInterval(refreshMeters, 250);
