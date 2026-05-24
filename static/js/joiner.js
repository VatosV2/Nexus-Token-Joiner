import { settings } from './settings.js';
import {
    addLog,
    updateStatsAndProgress,
    maskToken,
    getRandomDelay,
    checkTokens,
    getTokens,
    getProxies,
    getInvites
} from './utils.js';

let isJoining = false;
let joinStats = { successful: 0, failed: 0, pending: 0, total: 0, current: 0 };

export function initJoiner() {
    const joinBtn = document.getElementById("join-btn");
    const stopBtn = document.getElementById("stop-btn");
    const serverInviteInput = document.getElementById("server-invite");
    const singleInviteContainer = document.getElementById("single-invite-container");
    const multipleInvitesContainer = document.getElementById("multiple-invites-container");
    const tokenFillingCheckbox = document.getElementById("join-token-filling");

    tokenFillingCheckbox.addEventListener("change", function () {
        settings.join.token_filling = this.checked; 
        if (this.checked) {
            singleInviteContainer.style.display = "none";
            multipleInvitesContainer.style.display = "block";
        } else {
            singleInviteContainer.style.display = "block";
            multipleInvitesContainer.style.display = "none";
        }
    });

    joinBtn.addEventListener("click", () => {
        const tokens = getTokens();
        if (!checkTokens(tokens)) return;
        if (isJoining) return;

        let invitesToUse = [];
        if (settings.join.token_filling) {
            invitesToUse = getInvites();
            if (invitesToUse.length === 0) {
                addLog("Error: Please enter at least one server invite", "error");
                toast.error("Error", "Please enter at least one server invite");
                return;
            }
        } else {
            const invite = serverInviteInput.value.trim();
            if (!invite) {
                addLog("Error: Please enter a server invite code or URL", "error");
                toast.error("Error", "Please enter a server invite code or URL");
                return;
            }
            invitesToUse = [invite];
        }

        startJoining(tokens, invitesToUse, getProxies());
    });

    stopBtn.addEventListener("click", () => {
        isJoining = false;
        joinBtn.disabled = false;
        stopBtn.disabled = true;
        addLog("Joining process stopped by user");
    });
}

function startJoining(tokens, invites, proxies) {
    isJoining = true;
    document.getElementById("join-btn").disabled = true;
    document.getElementById("stop-btn").disabled = false;

    joinStats = {
        successful: 0,
        failed: 0,
        pending: tokens.length,
        total: tokens.length,
        current: 0,
    };
    updateStatsAndProgress(joinStats);

    if (settings.join.token_filling) {
        runTokenFilling(tokens, invites, proxies);
    } else {
        Joining(tokens, invites, proxies);
    }
}

function formatToken(raw) {
    if (!raw) return null;
    if (raw.includes(":")) {
        const parts = raw.split(":");
        return parts.length >= 3 ? parts[2].trim() : raw.trim();
    }
    return raw.trim();
}

function formatInvite(raw) {
    if (!raw) return null;
    if (raw.includes(".gg/")) return raw.split(".gg/")[1].trim();
    if (raw.includes("invite/")) return raw.split("invite/")[1].trim();
    return raw.trim();
}

async function runTokenFilling(tokens, invites, proxies) {
    try {
        const nickname = settings.appearance.nickname_enabled
            ? settings.appearance.nickname.replace("{random}", Math.floor(Math.random() * 10000))
            : "";

        const response = await window.pywebview.api.run_token_filling(
            invites.map(formatInvite).filter(Boolean),  
            tokens.map(formatToken).filter(Boolean),   
            proxies.filter(Boolean),                    
            nickname,
            settings.proxy.mode,
            settings.delay.min,
            settings.delay.max
        );

        if (response.success) {
            addLog("Token filling completed successfully");
            toast.success("Success", response.message || "Token filling completed");
        } else {
            addLog("Token filling failed: " + response.message, "error");
            toast.error("Error", response.message || "Token filling failed");
        }
    } catch (err) {
        addLog("Token filling error: " + err.message, "error");
        toast.error("Error", err.message);
    } finally {
        isJoining = false;
        document.getElementById("join-btn").disabled = false;
        document.getElementById("stop-btn").disabled = true;
        updateStatsAndProgress(joinStats);
    }
}

function Joining(tokens, invites, proxies) {
    const concurrency = 20;
    let currentIndex = 0;

    async function joinToken(token, index) {
        const inviteCode = formatInvite(invites[index % invites.length]);
        const nickname = settings.appearance.nickname_enabled
            ? settings.appearance.nickname.replace("{random}", Math.floor(Math.random() * 10000))
            : null;

        const proxy = settings.proxy.enabled ? (proxies[index % proxies.length] || "") : "";

        try {
            const response = await window.pywebview.api.join_server(
                token,
                inviteCode,
                nickname,
                proxy,
                settings.join.token_filling
            );

            if (response.success) joinStats.successful++;
            else joinStats.failed++;

            joinStats.current++;
            joinStats.pending--;
            updateStatsAndProgress(joinStats);
          

        } catch (err) {
            if (!settings.join.token_filling) {
                joinStats.failed++;
                joinStats.current++;
                joinStats.pending--;
                updateStatsAndProgress(joinStats);
            }
        }
    }


    async function processBatch() {
        if (!isJoining || currentIndex >= tokens.length) {
            isJoining = false;
            document.getElementById("join-btn").disabled = false;
            document.getElementById("stop-btn").disabled = true;
            addLog("Joining process completed");
            toast.info("Info", "Joining process completed");
            return;
        }

        const batch = [];
        for (let i = 0; i < concurrency && currentIndex < tokens.length; i++) {
            const token = formatToken(tokens[currentIndex]);
            if (token) {
                batch.push(joinToken(token, currentIndex));
            }
            currentIndex++;
        }
        await Promise.all(batch);

        const delay = settings.delay.enabled ? getRandomDelay(settings.delay.min, settings.delay.max) * 1000 : 200;
        setTimeout(processBatch, delay);
    }

    processBatch();
}
