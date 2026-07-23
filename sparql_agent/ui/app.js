(() => {
  const APP = "sparql_agent";
  const userId = localStorage.getItem("kchat.user") || `web-${crypto.randomUUID()}`;
  const sessionId = localStorage.getItem("kchat.session") || `chat-${crypto.randomUUID()}`;
  localStorage.setItem("kchat.user", userId);
  localStorage.setItem("kchat.session", sessionId);

  const $ = (selector) => document.querySelector(selector);
  const widget = $("#chat-widget");
  const launcher = $("#chat-launcher");
  const input = $("#chat-input");
  const messages = $("#messages");
  const sendButton = $("#send");
  const knownArtifacts = new Map();
  let artifactBlob = null;
  let artifactFilename = "artifact.txt";
  let totals = { input: 0, output: 0 };
  let contextWindowTokens = 0;

  function toggleChat(open) {
    widget.classList.toggle("closed", !open);
    launcher.style.display = open ? "none" : "grid";
    if (open) setTimeout(() => input.focus(), 150);
  }
  function toggleChatSize() {
    const maximized = widget.classList.toggle("maximized");
    const button = $("#chat-size");
    button.textContent = maximized ? "❐" : "⛶";
    button.setAttribute("aria-label", maximized ? "Restore chat size" : "Maximize chat");
    button.title = maximized ? "Restore chat size" : "Maximize chat";
  }
  $("#chat-size").onclick = toggleChatSize;
  $("#chat-close").onclick = () => toggleChat(false);
  launcher.onclick = () => toggleChat(true);
  $("#hero-chat").onclick = () => toggleChat(true);

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[c]);
  }
  function inlineMarkdown(value) {
    return value
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/__([^_]+)__/g, "<strong>$1</strong>")
      .replace(/\*([^*]+)\*/g, "<em>$1</em>")
      .replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_, label, url) => {
        const safe = /^(https?:\/\/|\/)/i.test(url) ? url : "#";
        return `<a href="${escapeHtml(safe)}" target="_blank" rel="noopener">${label}</a>`;
      });
  }
  function markdown(source) {
    const code = [];
    let text = escapeHtml(source || "").replace(/```([^\n]*)\n?([\s\S]*?)```/g, (_, language, body) => {
      const key = `@@CODE${code.length}@@`;
      code.push(`<pre><code class="language-${escapeHtml(language.trim())}">${body.replace(/^\n|\n$/g, "")}</code></pre>`);
      return key;
    });
    const lines = text.split("\n");
    let html = "", list = "";
    const closeList = () => { if (list) { html += `</${list}>`; list = ""; } };
    for (const line of lines) {
      if (/^@@CODE\d+@@$/.test(line)) { closeList(); html += line; continue; }
      const heading = line.match(/^(#{1,3})\s+(.+)/);
      const unordered = line.match(/^\s*[-*]\s+(.+)/);
      const ordered = line.match(/^\s*\d+\.\s+(.+)/);
      if (heading) { closeList(); const n = heading[1].length; html += `<h${n}>${inlineMarkdown(heading[2])}</h${n}>`; }
      else if (unordered) { if (list !== "ul") { closeList(); list = "ul"; html += "<ul>"; } html += `<li>${inlineMarkdown(unordered[1])}</li>`; }
      else if (ordered) { if (list !== "ol") { closeList(); list = "ol"; html += "<ol>"; } html += `<li>${inlineMarkdown(ordered[1])}</li>`; }
      else if (!line.trim()) { closeList(); }
      else { closeList(); html += `<p>${inlineMarkdown(line)}</p>`; }
    }
    closeList();
    return html.replace(/@@CODE(\d+)@@/g, (_, index) => code[Number(index)]);
  }

  function addMessage(role, text = "", extraClass = "") {
    const row = document.createElement("div");
    row.className = `message ${role} ${extraClass}`;
    const bubble = document.createElement("div");
    bubble.className = "bubble markdown";
    bubble.innerHTML = markdown(text);
    row.appendChild(bubble);
    messages.appendChild(row);
    messages.scrollTop = messages.scrollHeight;
    return { row, bubble };
  }

  async function ensureSession() {
    const path = `/apps/${APP}/users/${encodeURIComponent(userId)}/sessions/${encodeURIComponent(sessionId)}`;
    const existing = await fetch(path);
    if (existing.ok) return;
    const created = await fetch(path, { method: "POST", headers: {"content-type":"application/json"}, body: "{}" });
    if (!created.ok && created.status !== 409) throw new Error(`Could not create chat session (${created.status})`);
  }

  function renderUsage() {
    const used = totals.input + totals.output;
    const percentage = contextWindowTokens ? Math.min(100, used / contextWindowTokens * 100) : 0;
    const percentageLabel = !contextWindowTokens ? "—" : percentage > 0 && percentage < 0.1 ? "<0.1%" : `${percentage.toFixed(percentage < 10 ? 1 : 0)}%`;
    $("#input-tokens").textContent = totals.input.toLocaleString();
    $("#output-tokens").textContent = totals.output.toLocaleString();
    $("#context-percent").textContent = percentageLabel;
    $("#context-tokens").textContent = `${used.toLocaleString()} / ${contextWindowTokens ? contextWindowTokens.toLocaleString() : "—"}`;
    const meter = $("#context-meter");
    meter.value = percentage;
    meter.textContent = percentageLabel;
    meter.setAttribute("aria-valuetext", contextWindowTokens ? `${percentageLabel} context used` : "Context limit unavailable");
  }

  async function loadUiConfig() {
    try {
      const response = await fetch("/kchat-config");
      if (!response.ok) return;
      const config = await response.json();
      const limit = Number(config.contextWindowTokens);
      if (Number.isFinite(limit) && limit > 0) contextWindowTokens = limit;
    } catch {
      // Token counts remain available when model metadata cannot be loaded.
    } finally {
      renderUsage();
    }
  }

  function updateUsage(event) {
    const usage = event.usageMetadata || event.usage_metadata;
    if (!usage) return;
    const incoming = usage.promptTokenCount ?? usage.prompt_token_count ?? usage.inputTokenCount ?? usage.input_token_count;
    const outgoing = usage.candidatesTokenCount ?? usage.candidates_token_count ?? usage.outputTokenCount ?? usage.output_token_count;
    if (Number.isFinite(incoming)) totals.input = incoming;
    if (Number.isFinite(outgoing)) totals.output = outgoing;
    renderUsage();
  }

  loadUiConfig();

  function textFromEvent(event) {
    const parts = event.content?.parts || [];
    return parts.filter(part => part.text && !part.thought).map(part => part.text).join("");
  }

  async function consumeSse(response, onEvent) {
    if (!response.ok) throw new Error((await response.text()) || `Chat request failed (${response.status})`);
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const {value, done} = await reader.read();
      buffer += decoder.decode(value || new Uint8Array(), {stream: !done});
      const blocks = buffer.split(/\r?\n\r?\n/);
      buffer = blocks.pop() || "";
      for (const block of blocks) {
        const data = block.split(/\r?\n/).filter(line => line.startsWith("data:")).map(line => line.slice(5).trimStart()).join("\n");
        if (data && data !== "[DONE]") onEvent(JSON.parse(data));
      }
      if (done) break;
    }
    if (buffer.trim()) {
      const data = buffer.split(/\r?\n/).filter(line => line.startsWith("data:")).map(line => line.slice(5).trimStart()).join("\n");
      if (data && data !== "[DONE]") onEvent(JSON.parse(data));
    }
  }

  function artifactBase() {
    return `/apps/${APP}/users/${encodeURIComponent(userId)}/sessions/${encodeURIComponent(sessionId)}/artifacts`;
  }
  async function listArtifacts() {
    const response = await fetch(artifactBase());
    if (!response.ok) return [];
    const names = await response.json();
    const found = [];
    for (const name of names) {
      const versionsResponse = await fetch(`${artifactBase()}/${encodeURIComponent(name)}/versions`);
      if (!versionsResponse.ok) continue;
      const versions = await versionsResponse.json();
      for (const version of versions) found.push({name, version: Number(version)});
    }
    return found.sort((a, b) => a.version - b.version || a.name.localeCompare(b.name));
  }

  async function rememberExistingArtifacts() {
    for (const artifact of await listArtifacts()) knownArtifacts.set(`${artifact.name}:${artifact.version}`, true);
  }

  function artifactLabel(name) {
    if (name.endsWith(".rq")) return "SPARQL query";
    if (name.endsWith(".json")) return "JSON result";
    if (name.endsWith(".ttl")) return "Turtle result";
    return name;
  }

  async function attachNewArtifacts(row) {
    const found = [];
    for (const artifact of await listArtifacts()) {
      const key = `${artifact.name}:${artifact.version}`;
      if (!knownArtifacts.has(key)) {
        knownArtifacts.set(key, true);
        found.push(artifact);
      }
    }
    if (!found.length) return;
    const list = document.createElement("div");
    list.className = "artifact-list";
    list.setAttribute("aria-label", "Query artifacts");
    for (const artifact of found) {
      const pill = document.createElement("button");
      pill.type = "button";
      pill.className = "artifact-pill";
      pill.textContent = `${artifactLabel(artifact.name)} · v${artifact.version}`;
      pill.title = `Open ${artifact.name}`;
      pill.onclick = () => openArtifact(artifact.name, artifact.version);
      list.appendChild(pill);
    }
    row.querySelector(".bubble").appendChild(list);
    messages.scrollTop = messages.scrollHeight;
  }

  function decodeArtifactData(data) {
    // ADK serializes bytes with URL-safe base64, while window.atob expects
    // standard base64. Normalize its alphabet and restore omitted padding.
    const normalized = data.replace(/-/g, "+").replace(/_/g, "/");
    const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "=");
    const binary = atob(padded);
    return new TextDecoder().decode(Uint8Array.from(binary, c => c.charCodeAt(0)));
  }

  function formatSparql(source) {
    const protectedValues = [];
    const protectedQuery = source.trim().replace(/"""[\s\S]*?"""|'''[\s\S]*?'''|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|<[^>]*>|#[^\r\n]*/g, value => {
      const marker = `@@KCHAT${protectedValues.length}@@`;
      protectedValues.push(value);
      return marker;
    });
    const lines = protectedQuery
      .replace(/[\t\r\n ]+/g, " ")
      .replace(/\s*{\s*/g, " {\n")
      .replace(/\s*}\s*/g, "\n}\n")
      .replace(/\s+\.\s*/g, " .\n")
      .replace(/\s*;\s*/g, " ;\n")
      .replace(/\s+(?=(?:PREFIX|BASE|SELECT|ASK|CONSTRUCT|DESCRIBE|WHERE|OPTIONAL|FILTER|BIND|VALUES|GROUP\s+BY|ORDER\s+BY|HAVING|LIMIT|OFFSET|UNION|MINUS)\b)/gi, "\n")
      .split("\n")
      .map(line => line.trim())
      .filter(Boolean);
    let indent = 0;
    const formatted = lines.map(line => {
      const leadingClosings = line.match(/^}+/)?.[0].length || 0;
      indent = Math.max(0, indent - leadingClosings);
      const output = `${"  ".repeat(indent)}${line}`;
      const opens = (line.match(/{/g) || []).length;
      const closes = (line.match(/}/g) || []).length;
      indent = Math.max(0, indent + opens - closes + leadingClosings);
      return output;
    }).join("\n");
    return formatted.replace(/@@KCHAT(\d+)@@/g, (_, index) => protectedValues[Number(index)]);
  }

  async function openArtifact(name, version) {
    const modal = $("#artifact-modal");
    modal.classList.add("open"); modal.setAttribute("aria-hidden", "false");
    $("#artifact-title").textContent = name;
    $("#artifact-meta").textContent = `version ${version}`;
    $("#artifact-content").textContent = "Loading complete artifact…";
    try {
      const response = await fetch(`${artifactBase()}/${encodeURIComponent(name)}/versions/${version}`);
      if (!response.ok) throw new Error(`Could not load artifact (${response.status})`);
      const part = await response.json();
      const inline = part?.inlineData || part?.inline_data;
      let value = part?.text || "";
      let mime = "text/plain";
      if (inline?.data) {
        mime = inline.mimeType || inline.mime_type || mime;
        value = decodeArtifactData(inline.data);
      }
      artifactBlob = new Blob([value], {type: mime}); artifactFilename = name;
      let displayValue = value;
      if (name.toLowerCase().endsWith(".json") || mime.toLowerCase().includes("json")) {
        try { displayValue = JSON.stringify(JSON.parse(value), null, 2); }
        catch { /* Keep the original content if the artifact is not valid JSON. */ }
      } else if (name.toLowerCase().endsWith(".rq") || mime.toLowerCase().includes("sparql-query")) {
        displayValue = formatSparql(value);
      }
      $("#artifact-meta").textContent = `version ${version} · ${mime} · ${value.length.toLocaleString()} chars`;
      $("#artifact-content").textContent = displayValue;
    } catch (error) { $("#artifact-content").textContent = error.message; }
  }

  $("#artifact-close").onclick = () => { $("#artifact-modal").classList.remove("open"); $("#artifact-modal").setAttribute("aria-hidden", "true"); };
  $("#artifact-download").onclick = () => {
    if (!artifactBlob) return;
    const link = document.createElement("a"); link.href = URL.createObjectURL(artifactBlob); link.download = artifactFilename; link.click(); setTimeout(() => URL.revokeObjectURL(link.href), 1000);
  };

  // Drag the artifact window by its title bar.
  const drag = $("#artifact-drag"), artifactWindow = $(".artifact-window");
  drag.addEventListener("pointerdown", event => {
    if (event.target.closest("button")) return;
    const rect = artifactWindow.getBoundingClientRect(), dx = event.clientX - rect.left, dy = event.clientY - rect.top;
    drag.setPointerCapture(event.pointerId);
    const move = e => {
      artifactWindow.style.left = `${Math.max(0, Math.min(innerWidth - rect.width, e.clientX - dx))}px`;
      artifactWindow.style.top = `${Math.max(0, Math.min(innerHeight - 50, e.clientY - dy))}px`;
    };
    drag.addEventListener("pointermove", move);
    drag.addEventListener("pointerup", () => drag.removeEventListener("pointermove", move), {once:true});
  });

  async function submit(message) {
    addMessage("user", message);
    const assistant = addMessage("assistant", "");
    assistant.bubble.classList.add("typing");
    sendButton.disabled = true; input.disabled = true;
    let answer = "";
    try {
      await ensureSession();
      // Establish a baseline so pills on this message only represent queries run for it.
      await rememberExistingArtifacts();
      const response = await fetch("/run_sse", {method:"POST", headers:{"content-type":"application/json"}, body:JSON.stringify({appName:APP,userId,sessionId,streaming:true,newMessage:{role:"user",parts:[{text:message}]}})});
      await consumeSse(response, event => {
        updateUsage(event);
        const chunk = textFromEvent(event);
        if (chunk) {
          if (event.partial === false && answer && chunk.startsWith(answer)) answer = chunk;
          else answer += chunk;
          assistant.bubble.innerHTML = markdown(answer);
          messages.scrollTop = messages.scrollHeight;
        }
      });
      if (!answer) answer = "No text response was returned.";
      assistant.bubble.innerHTML = markdown(answer);
      await attachNewArtifacts(assistant.row);
    } catch (error) {
      assistant.row.classList.add("error");
      assistant.bubble.innerHTML = markdown(`**Chat error:** ${error.message}`);
    } finally {
      assistant.bubble.classList.remove("typing"); sendButton.disabled = false; input.disabled = false; input.focus();
    }
  }

  $("#chat-form").addEventListener("submit", event => {
    event.preventDefault(); const value = input.value.trim(); if (!value || sendButton.disabled) return;
    input.value = ""; input.style.height = "auto"; submit(value);
  });
  input.addEventListener("keydown", event => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); $("#chat-form").requestSubmit(); } });
  input.addEventListener("input", () => { input.style.height = "auto"; input.style.height = `${Math.min(input.scrollHeight, 100)}px`; });
})();
