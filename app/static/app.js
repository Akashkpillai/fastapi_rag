"use strict";

const state = { documents: [], selectedId: null, busy: false };
const $ = (id) => document.getElementById(id);

// ---------- API ----------

async function api(path, options = {}) {
  const response = await fetch(path, options);
  if (response.status === 204) return null;
  const body = await response.json().catch(() => null);
  if (!response.ok) throw new Error(errorText(body, response.status));
  return body;
}

function errorText(body, status) {
  const detail = body && body.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((item) => item.msg).join("; "); // FastAPI validation errors
  return `Request failed (${status})`;
}

// ---------- documents ----------

async function loadDocuments() {
  state.documents = await api("/document/");
  if (state.selectedId && !state.documents.some((doc) => doc.document_id === state.selectedId)) {
    state.selectedId = null;
  }
  renderDocuments();
}

function renderDocuments() {
  const count = state.documents.length;
  const items = [documentItem(null, "All documents", `${count} document${count === 1 ? "" : "s"}`)];
  for (const doc of state.documents) {
    items.push(documentItem(doc.document_id, doc.filename, `${doc.page_count} pages · ${doc.chunk_count} chunks`));
  }
  $("doc-list").replaceChildren(...items);

  const selected = state.documents.find((doc) => doc.document_id === state.selectedId);
  $("scope-name").textContent = selected ? selected.filename : "All documents";
}

function documentItem(id, name, meta) {
  const item = el("li", "doc" + (id === state.selectedId ? " selected" : ""));

  const select = el("button", "doc-select");
  select.type = "button";
  select.append(el("span", "doc-name", name), el("span", "doc-meta", meta));
  select.addEventListener("click", () => {
    state.selectedId = id;
    renderDocuments();
    $("question").focus();
  });
  item.append(select);

  if (id) {
    const remove = el("button", "doc-delete");
    remove.type = "button";
    remove.setAttribute("aria-label", `Delete ${name}`);
    remove.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/></svg>';
    remove.addEventListener("click", () => deleteDocument(id, name));
    item.append(remove);
  }
  return item;
}

async function deleteDocument(id, name) {
  if (!confirm(`Delete "${name}"? This removes it and all its chunks from the database.`)) return;
  try {
    await api(`/document/${encodeURIComponent(id)}`, { method: "DELETE" });
    await loadDocuments();
    showUploadStatus(`Deleted ${name}.`);
  } catch (error) {
    showUploadStatus(error.message, true);
  }
}

// ---------- upload ----------

function showUploadStatus(message, isError = false) {
  const status = $("upload-status");
  status.textContent = message;
  status.classList.toggle("error", isError);
  status.hidden = false;
}

async function uploadFile(file) {
  if (!file) return;
  if (!file.name.toLowerCase().endsWith(".pdf")) {
    showUploadStatus("Only PDF files can be uploaded.", true);
    return;
  }
  // Some systems leave the type empty; the server checks for application/pdf
  const pdf = file.type === "application/pdf" ? file : new File([file], file.name, { type: "application/pdf" });
  const form = new FormData();
  form.append("file", pdf);

  const dropzone = $("dropzone");
  dropzone.classList.add("busy");
  showUploadStatus(`Reading and indexing ${file.name}… this can take up to a minute.`);
  try {
    const summary = await api("/document/upload", { method: "POST", body: form });
    state.selectedId = summary.document_id;
    await loadDocuments();
    let message = `Ready: ${summary.filename} (${summary.page_count} pages, ${summary.chunk_count} chunks).`;
    if (summary.empty_pages.length) message += ` ${summary.empty_pages.length} page(s) had no text.`;
    showUploadStatus(message);
  } catch (error) {
    showUploadStatus(error.message, true);
  } finally {
    dropzone.classList.remove("busy");
    $("file-input").value = "";
  }
}

// ---------- chat ----------

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function addMessage(role, content) {
  $("empty-state")?.remove();
  const message = el("div", `message ${role}`);
  const bubble = el("div", "bubble");
  if (typeof content === "string") bubble.textContent = content;
  else bubble.append(content);
  message.append(bubble);
  $("messages").append(message);
  message.scrollIntoView({ behavior: "smooth", block: "end" });
  return message;
}

function typingIndicator() {
  const dots = el("div", "typing");
  dots.setAttribute("aria-label", "Thinking");
  dots.append(el("span"), el("span"), el("span"));
  return dots;
}

function answerContent(result) {
  const content = el("div");
  const body = el("div", "markdown");
  body.innerHTML = renderMarkdown(result.answer); // safe: renderMarkdown escapes HTML first
  content.append(body);

  if (result.sources && result.sources.length) {
    // One chip per cited page; open it to read the excerpts the answer was based on
    const byPage = new Map();
    for (const source of result.sources) {
      if (!byPage.has(source.page_number)) byPage.set(source.page_number, []);
      byPage.get(source.page_number).push(source.text);
    }
    const pages = el("div", "source-pages");
    for (const [page, texts] of byPage) {
      const details = el("details", "source");
      details.append(el("summary", null, `Page ${page}`), el("blockquote", null, excerpt(texts.join(" … "))));
      pages.append(details);
    }
    const sources = el("div", "sources");
    sources.append(el("p", "sources-title", "Sources"), pages);
    content.append(sources);
  }
  return content;
}

function excerpt(text, limit = 900) {
  // PDF text breaks lines where the page did; join them so the excerpt reads as prose
  const clean = text.replace(/\s*\n\s*/g, " ").replace(/\s{2,}/g, " ").trim();
  return clean.length > limit ? clean.slice(0, limit) + "…" : clean;
}

async function ask(question) {
  if (state.busy || !question.trim()) return;
  setBusy(true);
  addMessage("user", question);
  const pending = addMessage("assistant", typingIndicator());

  const payload = { question };
  if (state.selectedId) payload.document_id = state.selectedId;
  try {
    const result = await api("/question", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    pending.querySelector(".bubble").replaceChildren(answerContent(result));
  } catch (error) {
    pending.className = "message error";
    pending.querySelector(".bubble").textContent = error.message;
  } finally {
    setBusy(false);
    pending.scrollIntoView({ behavior: "smooth", block: "end" });
  }
}

function setBusy(busy) {
  state.busy = busy;
  $("send").disabled = busy;
}

// ---------- markdown (small and safe: HTML is escaped before any formatting) ----------

function escapeHtml(text) {
  const entities = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
  return text.replace(/[&<>"']/g, (char) => entities[char]);
}

function inlineMarkdown(text) {
  return text
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[^*\w])\*(?!\s)([^*]+?)\*(?![*\w])/g, "$1<em>$2</em>");
}

const LIST_ITEM = /^(\s*)([-*•]|\d+[.)])\s+(.*)$/;
const TABLE_ROW = /^\s*\|.*\|\s*$/;
const TABLE_RULE = /^\s*\|?\s*:?-{3,}/;
const HEADING = /^(#{1,4})\s+(.*)$/;

// Renders the list starting at lines[start]; more-indented items become a nested list.
// Returns [html, index of the first line after the list].
function renderList(lines, start, indent) {
  const ordered = /\d/.test(lines[start].match(LIST_ITEM)[2]);
  const items = [];
  let i = start;

  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) {
      // A blank line only ends the list if the next text isn't another item of it
      let next = i + 1;
      while (next < lines.length && !lines[next].trim()) next++;
      const nextItem = (lines[next] || "").match(LIST_ITEM);
      if (nextItem && nextItem[1].length >= indent) { i = next; continue; }
      break;
    }

    const item = line.match(LIST_ITEM);
    if (!item) {
      if (items.length && /^\s{2,}\S/.test(line)) {
        items[items.length - 1].text += " " + line.trim(); // wrapped continuation line
        i++;
        continue;
      }
      break;
    }

    const itemIndent = item[1].length;
    if (itemIndent < indent) break;
    if (itemIndent > indent && items.length) {
      let child;
      [child, i] = renderList(lines, i, itemIndent);
      items[items.length - 1].children += child;
      continue;
    }
    items.push({ text: item[3], children: "" });
    i++;
  }

  const tag = ordered ? "ol" : "ul";
  const body = items.map((item) => `<li>${inlineMarkdown(item.text)}${item.children}</li>`).join("");
  return [`<${tag}>${body}</${tag}>`, i];
}

function renderMarkdown(markdown) {
  const lines = escapeHtml(markdown.replace(/\r/g, "")).split("\n");
  const html = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) { i++; continue; }

    const heading = line.match(HEADING);
    if (heading) {
      const level = Math.min(heading[1].length + 2, 6); // keep answer headings small
      html.push(`<h${level}>${inlineMarkdown(heading[2])}</h${level}>`);
      i++;
      continue;
    }

    if (TABLE_ROW.test(line) && TABLE_RULE.test(lines[i + 1] || "")) {
      const cells = (row) => row.trim().replace(/^\||\|$/g, "").split("|").map((cell) => inlineMarkdown(cell.trim()));
      const head = cells(line);
      i += 2;
      const rows = [];
      while (i < lines.length && TABLE_ROW.test(lines[i])) rows.push(cells(lines[i++]));
      html.push(
        `<div class="table-wrap"><table><thead><tr>${head.map((c) => `<th>${c}</th>`).join("")}</tr></thead>` +
        `<tbody>${rows.map((r) => `<tr>${r.map((c) => `<td>${c}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`
      );
      continue;
    }

    const first = line.match(LIST_ITEM);
    if (first) {
      let listHtml;
      [listHtml, i] = renderList(lines, i, first[1].length);
      html.push(listHtml);
      continue;
    }

    // Paragraph: always takes this line, then following lines until a blank line or another block
    const paragraph = [line.trim()];
    i++;
    while (i < lines.length && lines[i].trim() && !HEADING.test(lines[i]) && !LIST_ITEM.test(lines[i]) && !TABLE_ROW.test(lines[i])) {
      paragraph.push(lines[i++].trim());
    }
    html.push(`<p>${inlineMarkdown(paragraph.join(" "))}</p>`);
  }
  return html.join("");
}

// ---------- wiring ----------

function setup() {
  const input = $("question");

  $("composer").addEventListener("submit", (event) => {
    event.preventDefault();
    const question = input.value.trim();
    if (!question) return;
    input.value = "";
    input.style.height = "";
    ask(question);
  });

  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      $("composer").requestSubmit();
    }
  });

  input.addEventListener("input", () => {
    input.style.height = "auto";
    input.style.height = `${input.scrollHeight}px`;
  });

  for (const button of $("suggestions").querySelectorAll("button")) {
    button.addEventListener("click", () => ask(button.textContent));
  }

  const dropzone = $("dropzone");
  $("file-input").addEventListener("change", (event) => uploadFile(event.target.files[0]));
  dropzone.addEventListener("dragover", (event) => {
    event.preventDefault();
    dropzone.classList.add("dragging");
  });
  dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragging"));
  dropzone.addEventListener("drop", (event) => {
    event.preventDefault();
    dropzone.classList.remove("dragging");
    uploadFile(event.dataTransfer.files[0]);
  });

  loadDocuments().catch((error) => showUploadStatus(`Couldn't load documents: ${error.message}`, true));
}

setup();
