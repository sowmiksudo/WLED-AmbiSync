const elements = {
    moodPanel: document.getElementById('mood-panel'),
    currentMood: document.getElementById('current-mood'),
    bgEffect: document.querySelector('.bg-effect'),
    brightnessSlider: document.getElementById('base-brightness'),
    brightnessVal: document.getElementById('brightness-val'),
    bassSlider: document.getElementById('bass-sensitivity'),
    bassVal: document.getElementById('bass-val'),
    fpsSlider: document.getElementById('fps-target'),
    fpsVal: document.getElementById('fps-val'),
    moodSelect: document.getElementById('manual-mood'),
    audioSyncBtn: document.getElementById('audio-sync-btn'),
    wledIp: document.getElementById('wled-ip'),
    totalLeds: document.getElementById('total-leds'),
    refreshBtn: document.getElementById('refresh-btn'),
};

let debounceTimer;

async function fetchState() {
    try {
        const response = await fetch('/api/state');
        if (!response.ok) throw new Error('Network error');
        const data = await response.json();
        updateUI(data);
    } catch (err) {
        console.error("Failed to fetch state:", err);
    }
}

function updateUI(data) {
    const config = data.config;
    const mood = data.current_mood;

    // Update Mood info
    if (config.MANUAL_MOOD === "Smart" || !config.MANUAL_MOOD) {
        elements.currentMood.innerText = `Smart Auto: ${mood}`;
    } else {
        elements.currentMood.innerText = `Locked: ${mood}`;
    }

    // Update Mood Color themes
    if (mood.includes("Action")) {
        elements.moodPanel.style.background = "var(--mood-Action)";
        elements.bgEffect.style.background = "radial-gradient(circle, rgba(255, 60, 60, 0.4) 0%, transparent 60%)";
    } else if (mood.includes("Nature")) {
        elements.moodPanel.style.background = "var(--mood-Nature)";
        elements.bgEffect.style.background = "radial-gradient(circle, rgba(60, 255, 120, 0.4) 0%, transparent 60%)";
    } else if (mood.includes("Horror")) {
        elements.moodPanel.style.background = "var(--mood-Horror)";
        elements.bgEffect.style.background = "radial-gradient(circle, rgba(80, 50, 255, 0.3) 0%, transparent 60%)";
    } else if (mood.includes("Gaming")) {
        elements.moodPanel.style.background = "var(--mood-Gaming)";
        elements.bgEffect.style.background = "radial-gradient(circle, rgba(230, 50, 255, 0.4) 0%, transparent 60%)";
    } else if (mood.includes("Text")) {
        elements.moodPanel.style.background = "var(--mood-Static)";
        elements.bgEffect.style.background = "radial-gradient(circle, rgba(200, 200, 255, 0.2) 0%, transparent 60%)";
    } else if (mood.includes("Sci-Fi")) {
        elements.moodPanel.style.background = "var(--mood-SciFi)";
        elements.bgEffect.style.background = "radial-gradient(circle, rgba(45, 212, 191, 0.4) 0%, transparent 60%)";
    } else if (mood.includes("Sports")) {
        elements.moodPanel.style.background = "var(--mood-Sports)";
        elements.bgEffect.style.background = "radial-gradient(circle, rgba(234, 179, 8, 0.4) 0%, transparent 60%)";
    } else if (mood.includes("Movie")) {
        elements.moodPanel.style.background = "var(--mood-Movie)";
        elements.bgEffect.style.background = "radial-gradient(circle, rgba(217, 119, 6, 0.3) 0%, transparent 60%)";
    } else {
        elements.moodPanel.style.background = "var(--mood-Mirror)";
        elements.bgEffect.style.background = "radial-gradient(circle, rgba(88, 166, 255, 0.4) 0%, transparent 60%)";
    }

    // Update form values if they aren't currently being dragged
    if (document.activeElement !== elements.brightnessSlider) {
        elements.brightnessSlider.value = config.BASE_BRIGHTNESS;
        elements.brightnessVal.innerText = config.BASE_BRIGHTNESS.toFixed(2);
    }
    if (document.activeElement !== elements.bassSlider) {
        elements.bassSlider.value = config.BASS_SENSITIVITY;
        elements.bassVal.innerText = config.BASS_SENSITIVITY.toFixed(1);
    }
    if (document.activeElement !== elements.fpsSlider) {
        elements.fpsSlider.value = config.FPS_TARGET;
        elements.fpsVal.innerText = config.FPS_TARGET;
    }

    if (document.activeElement !== elements.moodSelect) {
        const currentManual = config.MANUAL_MOOD || "Smart";
        elements.moodSelect.value = currentManual;
    }

    // Update Audio Button State
    const actionState = elements.audioSyncBtn.getAttribute('data-action-state');
    if (actionState !== "animating") {
        const isActive = config.AUDIO_SYNC_ENABLED !== false;
        elements.audioSyncBtn.dataset.active = isActive;
        if (isActive) {
            elements.audioSyncBtn.className = "btn btn-audio btn-audio-active";
            elements.audioSyncBtn.innerText = "Bass Audio Sync: ON";
        } else {
            elements.audioSyncBtn.className = "btn btn-audio btn-audio-inactive";
            elements.audioSyncBtn.innerText = "Bass Audio Sync: OFF";
        }
    }

    // Update infomation text
    elements.wledIp.innerText = config.WLED_IP;
    const total = config.LEDS_LEFT + config.LEDS_RIGHT + config.LEDS_TOP;
    elements.totalLeds.innerText = total;
}

function updateConfig(payload) {
    fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    }).catch(err => console.error("Update failed:", err));
}

function setupListeners() {
    elements.brightnessSlider.addEventListener('input', (e) => {
        elements.brightnessVal.innerText = parseFloat(e.target.value).toFixed(2);
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
            updateConfig({ BASE_BRIGHTNESS: parseFloat(e.target.value) });
        }, 100);
    });

    elements.bassSlider.addEventListener('input', (e) => {
        elements.bassVal.innerText = parseFloat(e.target.value).toFixed(1);
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
            updateConfig({ BASS_SENSITIVITY: parseFloat(e.target.value) });
        }, 100);
    });

    elements.fpsSlider.addEventListener('input', (e) => {
        elements.fpsVal.innerText = e.target.value;
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
            updateConfig({ FPS_TARGET: parseInt(e.target.value) });
        }, 300);
    });

    elements.moodSelect.addEventListener('change', (e) => {
        const selectedMood = e.target.value;
        updateConfig({ MANUAL_MOOD: selectedMood });
    });

    elements.audioSyncBtn.addEventListener('click', (e) => {
        // Lock out UI updates while animating bounce
        e.target.setAttribute('data-action-state', 'animating');
        const isActive = e.target.dataset.active === 'true';
        const newState = !isActive;

        // Optimistic UI update
        e.target.dataset.active = newState;
        if (newState) {
            e.target.className = "btn btn-audio btn-audio-active";
            e.target.innerText = "Bass Audio Sync: ON";
        } else {
            e.target.className = "btn btn-audio btn-audio-inactive";
            e.target.innerText = "Bass Audio Sync: OFF";
        }

        updateConfig({ AUDIO_SYNC_ENABLED: newState });
        setTimeout(() => e.target.removeAttribute('data-action-state'), 500);
    });

    elements.refreshBtn.addEventListener('click', fetchState);
}

// Init
setupListeners();
fetchState();
setInterval(fetchState, 1000); // Poll status every second
