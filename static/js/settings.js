import { addLog } from './utils.js';

export let settings = {
    delay: { enabled: false, min: 2, max: 4 },
    proxy: { enabled: true, mode: "rotating" },
    captcha: { service: "anysolver", subservice: "Capless", api_key: "", timeout: 60, enabled: true },
    join: { token_filling: false, bypass_rules: true, bypass_onboarding: true, bypass_restorecord: false, timeout: 20 },
    appearance: { nickname_enabled: false, nickname: "Member {random}" },
    vc_joiner: { mute: true, deaf: false,  randomize_options: false }
};

let listenersAttached = false;  

export async function loadSettings() {
    try {
        const configSettings = await window.pywebview.api.load_config_json();
        if (configSettings) {
            deepMerge(settings, configSettings);  
        } else if (localStorage.getItem("nexusSettings")) {
            deepMerge(settings, JSON.parse(localStorage.getItem("nexusSettings")));
        }
    } catch (err) {
        addLog("Failed to load config.json: " + err.message, "error");
        if (localStorage.getItem("nexusSettings")) {
            deepMerge(settings, JSON.parse(localStorage.getItem("nexusSettings")));
        }
    }

    loadSettingsIntoUI();
}

export function loadSettingsIntoUI() {
    document.getElementById("delay-enabled").checked = settings.delay.enabled;
    document.getElementById("delay-min").value = settings.delay.min;
    document.getElementById("delay-max").value = settings.delay.max;

    document.getElementById("proxy-enabled").checked = settings.proxy.enabled;
    document.getElementById("proxy-mode").value = settings.proxy.mode;

    document.getElementById("captcha-enabled").checked = settings.captcha.enabled;
    document.getElementById("captcha-subservice").value = settings.captcha.subservice;
    document.getElementById("captcha-api-key").value = settings.captcha.api_key;
    document.getElementById("captcha-timeout").value = settings.captcha.timeout;

    document.getElementById("appearance-nickname-enabled").checked = settings.appearance.nickname_enabled;
    document.getElementById("appearance-nickname").value = settings.appearance.nickname;

    document.getElementById("vc-join-muted").checked = settings.vc_joiner.mute;
    document.getElementById("vc-join-deafened").checked = settings.vc_joiner.deaf;
    document.getElementById("vc-randomize-options").checked = settings.vc_joiner.randomize_options;

    document.getElementById("join-token-filling").checked = settings.join.token_filling;
    document.getElementById("join-bypass-rules").checked = settings.join.bypass_rules;
    document.getElementById("join-bypass-onboarding").checked = settings.join.bypass_onboarding;
    document.getElementById("join-bypass-restorecord").checked = settings.join.bypass_restorecord;
    document.getElementById("join-timeout").value = settings.join.timeout;


    if (!listenersAttached) {
        attachInstantSaveListeners();
        listenersAttached = true;
    }
}

function attachInstantSaveListeners() {
    const inputs = document.querySelectorAll(
        "#delay-enabled, #delay-min, #delay-max, #proxy-enabled, #proxy-mode," +
        "#captcha-enabled, #captcha-subservice, #captcha-api-key, #captcha-timeout," + 
        "#appearance-nickname-enabled, #appearance-nickname," +
        "#vc-join-muted, #vc-join-deafened, #vc-randomize-options," +  
        "#join-token-filling, #join-bypass-rules, #join-bypass-onboarding, #join-bypass-restorecord, #join-timeout"
    );

    inputs.forEach(input => {
        input.addEventListener("change", saveSettingsInstant);
        if (input.type !== "checkbox") {
            input.addEventListener("input", debounce(saveSettingsInstant, 300));
        }
    });
}

function debounce(fn, ms) {
    let timer;
    return function(...args) {
        clearTimeout(timer);
        timer = setTimeout(() => fn.apply(this, args), ms);
    };
}

async function saveSettingsInstant() {
    settings.delay.enabled = document.getElementById("delay-enabled").checked;
    settings.delay.min = Number(document.getElementById("delay-min").value);
    settings.delay.max = Number(document.getElementById("delay-max").value);

    settings.proxy.enabled = document.getElementById("proxy-enabled").checked;
    settings.proxy.mode = document.getElementById("proxy-mode").value;

    settings.captcha.enabled = document.getElementById("captcha-enabled").checked;
    settings.captcha.subservice = document.getElementById("captcha-subservice").value; 
    settings.captcha.api_key = document.getElementById("captcha-api-key").value;
    settings.captcha.timeout = Number(document.getElementById("captcha-timeout").value);

    settings.appearance.nickname_enabled = document.getElementById("appearance-nickname-enabled").checked;
    settings.appearance.nickname = document.getElementById("appearance-nickname").value;

    settings.vc_joiner.mute = document.getElementById("vc-join-muted").checked;
    settings.vc_joiner.deaf = document.getElementById("vc-join-deafened").checked;
    settings.vc_joiner.randomize_options = document.getElementById("vc-randomize-options").checked;

    settings.join.token_filling = document.getElementById("join-token-filling").checked;
    settings.join.bypass_rules = document.getElementById("join-bypass-rules").checked;
    settings.join.bypass_onboarding = document.getElementById("join-bypass-onboarding").checked;
    settings.join.bypass_restorecord = document.getElementById("join-bypass-restorecord").checked;
    settings.join.timeout = Number(document.getElementById("join-timeout").value);


    localStorage.setItem("nexusSettings", JSON.stringify(settings));

    try {
        await window.pywebview.api.update_config_json(settings);
    } catch (err) {
        addLog("Failed to update config.json: " + err.message, "error");
    }
}

export async function loadSettingsFromBackend() {
    if (!window.pywebview || !window.pywebview.api) {
        setTimeout(loadSettingsFromBackend, 100);
        return;
    }

    try {
        const backendSettings = await window.pywebview.api.load_config_json();
        if (backendSettings) {
            deepMerge(settings, backendSettings);
            loadSettingsIntoUI();
        } else if (localStorage.getItem("nexusSettings")) {
            deepMerge(settings, JSON.parse(localStorage.getItem("nexusSettings")));
            loadSettingsIntoUI();
        }
    } catch (err) {
        console.error("Failed to load backend settings:", err);
        if (localStorage.getItem("nexusSettings")) {
            deepMerge(settings, JSON.parse(localStorage.getItem("nexusSettings")));
            loadSettingsIntoUI();
        }
    }
}

function deepMerge(target, source) {
    for (const key in source) {
        if (source[key] && typeof source[key] === "object" && !Array.isArray(source[key])) {
            if (!target[key] || typeof target[key] !== "object") target[key] = {};
            deepMerge(target[key], source[key]);
        } else {
            target[key] = source[key];
        }
    }
    return target;
}