import { addLog, setTokens, setProxies, setInvites, setPfps, setSelectedPfp } from './utils.js';

export function setupDragAndDrop() {
  function setup(dropArea, fileInput, callback) {
    if (!dropArea || !fileInput) return;

    fileInput.addEventListener("change", e => {
      const file = e.target.files[0];
      if (file) callback(file);
    });

    ["dragenter", "dragover", "dragleave", "drop"].forEach(event =>
      dropArea.addEventListener(event, e => {
        e.preventDefault();
        e.stopPropagation();
      }, false)
    );

    ["dragenter", "dragover"].forEach(event =>
      dropArea.addEventListener(event, () => dropArea.classList.add("drag-over"), false)
    );

    ["dragleave", "drop"].forEach(event =>
      dropArea.addEventListener(event, () => dropArea.classList.remove("drag-over"), false)
    );

    dropArea.addEventListener("drop", e => {
      const file = e.dataTransfer.files[0];
      if (file) callback(file);
    }, false);
  }

  setup(
    document.getElementById("tokens-drag-area"),
    document.getElementById("token-file"),
    (file) => {
      document.getElementById("file-info").textContent = `Selected: ${file.name}`;
      const reader = new FileReader();
      reader.onload = e => {
        let lines = e.target.result.split(/\r?\n/).filter(x => x.trim());

        const tokens = lines.map(line => {
          const parts = line.split(":");
          return parts.length === 3 ? parts[2] : parts.length === 2 ? parts[1] : parts[0];
        }).filter(Boolean);

        document.getElementById("tokens-textarea").value = tokens.join("\n");
        setTokens(tokens);
        addLog(`Loaded ${tokens.length} tokens from file`);
        toast.success("Tokens Loaded", `${tokens.length} tokens ready`);
      };
      reader.readAsText(file);
    }
  );


  setup(
    document.getElementById("proxies-drag-area"),
    document.getElementById("proxy-file"),
    (file) => {
      document.getElementById("proxy-file-info").textContent = `Selected: ${file.name}`;
      const reader = new FileReader();
      reader.onload = e => {
        const proxies = e.target.result.split(/\r?\n/).filter(x => x.trim());
        document.getElementById("proxy-list").value = proxies.join("\n");
        setProxies(proxies);
        addLog(`Loaded ${proxies.length} proxies from file`);
        toast.success("Proxies Loaded", `${proxies.length} proxies ready`);
      };
      reader.readAsText(file);
    }
  );

  setup(
    document.getElementById("invites-drag-area"),
    document.getElementById("invites-file"),
    (file) => {
      document.getElementById("invites-file-info").textContent = `Selected: ${file.name}`;
      const reader = new FileReader();
      reader.onload = e => {
        const invites = e.target.result.split(/\r?\n/).filter(x => x.trim());
        document.getElementById("multiple-invites").value = invites.join("\n");
        setInvites(invites);
        addLog(`Loaded ${invites.length} invites from file`);
        toast.success("Invites Loaded", `${invites.length} invites ready`);
      };
      reader.readAsText(file);
    }
  );

  setup(
    document.getElementById("single-pfp-upload"),
    document.getElementById("pfp-file"),
    (file) => {
      if (!file.type.startsWith("image/")) {
        addLog("Error: Please select a valid image file", "error");
        toast.error("Error", "Please select a valid image file");
        return;
      }
      document.getElementById("pfp-file-info").textContent = `Selected: ${file.name}`;
      const reader = new FileReader();
      reader.onload = e => {
        setSelectedPfp(e.target.result);
        document.getElementById("pfp-preview").innerHTML = `<img src="${e.target.result}" alt="Profile Picture">`;
        addLog(`Selected profile picture: ${file.name}`);
        toast.success("PFP Selected", file.name);
      };
      reader.readAsDataURL(file);
    }
  );

  setup(
    document.getElementById("pfp-folder-upload"),
    document.getElementById("pfp-folder"),
    async (file) => {
      if (!(file.type === "application/zip" || file.type === "application/x-zip-compressed")) {
        addLog("Error: Please select a valid ZIP file", "error");
        toast.error("Error", "Please select a valid ZIP file");
        return;
      }

      document.getElementById("pfp-folder-info").textContent = `Selected: ${file.name}`;

      try {
        const zip = new JSZip();
        const content = await zip.loadAsync(file);

        const pfps = [];
        for (const [filename, zipEntry] of Object.entries(content.files)) {
          if (zipEntry.dir) continue;
          if (!/\.(png|jpg|jpeg|gif)$/i.test(filename)) continue;

          const base64 = await zipEntry.async("base64");
          const mime = filename.endsWith(".png") ? "image/png" :
                      filename.endsWith(".gif") ? "image/gif" : "image/jpeg";
          pfps.push(`data:${mime};base64,${base64}`);
        }

        if (pfps.length === 0) {
          addLog("No valid image files found in ZIP", "warn");
          toast.warn("No Images", "ZIP did not contain PNG/JPG/GIF images");
          return;
        }

        setPfps(pfps);
        addLog(`Loaded ${pfps.length} PFP images from ZIP`);
        toast.success("PFP Pack Loaded", `${pfps.length} images ready`);

      } catch (error) {
        console.error(error);
        addLog("Error extracting ZIP", "error");
        toast.error("Error", "Failed to extract ZIP");
      }
    }
  );
}

function setupManualInputListener(elementId, setFunc, type = "default") {
  const el = document.getElementById(elementId);
  if (!el) return;

  el.addEventListener("input", e => {
    const items = e.target.value
      .split(/\r?\n/)
      .map(x => x.trim())
      .filter(Boolean);

    let processedItems = items;

    if (type === "tokens") {
      processedItems = items.map(line => {
        const parts = line.split(":");
        return parts.length === 3 ? parts[2] : parts.length === 2 ? parts[1] : parts[0];
      }).filter(Boolean);
    }

    setFunc(processedItems);
  });
}


setupManualInputListener("tokens-textarea", setTokens, "tokens");
setupManualInputListener("proxy-list", setProxies, "Proxies");
setupManualInputListener("multiple-invites", setInvites, "Invites");
