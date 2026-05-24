import { loadSettingsFromBackend } from './settings.js';

export async function initLoading() {
    const progressBar = document.getElementById("loading-progress");
    const progressText = document.getElementById("loading-status");
    const overlay = document.getElementById("loading-overlay");
    const mainContainer = document.getElementById("main-container");

    if (!progressBar || !progressText || !overlay || !mainContainer) {
        console.error("Loading elements not found in DOM!");
        return;
    }

    const steps = [
        { progress: 10, message: "Initializing..." },
        { progress: 25, message: "Checking Internet connection..." },
        { progress: 40, message: "Building headers..." },
        { progress: 60, message: "Loading modules..." },
        { progress: 90, message: "Almost ready..." },
        { progress: 100, message: "Complete!" },
    ];

    const updateProgress = (step) => {
        progressBar.style.width = step.progress + "%";
        progressText.textContent = step.message;
    };

    updateProgress(steps[0]);
    await new Promise(r => setTimeout(r, 200));

    updateProgress(steps[1]);
    let internetOk = false;
    try {
        const response = await fetch("https://www.google.com/", { mode: "no-cors" });
        internetOk = true; 
    } catch {}
    if (!internetOk) {
        updateProgress({ progress: 25, message: "Internet not detected!" });
        return;
    }
    await new Promise(r => setTimeout(r, 300));

    updateProgress(steps[2]);
    try {
        await window.pywebview.api.prepare_headers();
        console.log("Headers built successfully");
    } catch (err) {
        console.error("Failed building headers", err);
    }
    await new Promise(r => setTimeout(r, 200));

    updateProgress(steps[3]);
    try {
        await loadSettingsFromBackend();
    } catch (err) {
        console.error("Module loading failed", err);
    }
    await new Promise(r => setTimeout(r, 300));

    updateProgress(steps[4]);
    await new Promise(r => setTimeout(r, 200));

    updateProgress(steps[5]);
    await new Promise(r => setTimeout(r, 200));

    overlay.style.display = "none";
    mainContainer.style.display = "block";

    console.log("Loading complete!");
}
