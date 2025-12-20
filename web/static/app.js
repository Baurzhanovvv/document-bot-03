// web/static/app.js

const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("fileInput");
const uploadBtn = document.getElementById("uploadBtn");
const statusEl = document.getElementById("uploadStatus");
const fileList = document.getElementById("fileList");
const tpl = document.getElementById("fileCardTpl");

let queue = [];

// drag & drop
["dragenter","dragover"].forEach(evt => dropzone.addEventListener(evt, e => {
  e.preventDefault(); e.stopPropagation(); dropzone.classList.add("dragover");
}));
["dragleave","drop"].forEach(evt => dropzone.addEventListener(evt, e => {
  e.preventDefault(); e.stopPropagation(); dropzone.classList.remove("dragover");
}));
dropzone.addEventListener("drop", e => {
  const files = Array.from(e.dataTransfer.files || []);
  queue.push(...files);
  statusEl.textContent = `Выбрано файлов: ${queue.length}`;
});

dropzone.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", e => {
  const files = Array.from(e.target.files || []);
  queue.push(...files);
  statusEl.textContent = `Выбрано файлов: ${queue.length}`;
});

uploadBtn.addEventListener("click", async () => {
  if (!queue.length) { statusEl.textContent = "Нет файлов для загрузки"; return; }
  uploadBtn.disabled = true;
  try {
    const form = new FormData();
    for (const f of queue) form.append("file", f, f.name);
    const resp = await fetch("/api/upload", { method: "POST", body: form });
    if (!resp.ok) throw new Error("upload failed");
    const data = await resp.json();
    statusEl.textContent = `Загружено: ${data.saved.join(", ")}`;
    queue = [];
    await refreshList();
  } catch (e) {
    console.error(e);
    statusEl.textContent = "Ошибка загрузки";
  } finally {
    uploadBtn.disabled = false;
    fileInput.value = "";
  }
});
async function deleteFile(pathRel) {
  const encoded = pathRel.split('/').map(encodeURIComponent).join('/');
  const res = await fetch(`/api/files/${encoded}`, { method: 'DELETE' });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data?.error || data || 'Delete failed');
  }
}
async function refreshList() {
  fileList.innerHTML = "";
  const resp = await fetch("/api/files");
  const data = await resp.json();
  for (const f of data.files) {
    const node = tpl.content.firstElementChild.cloneNode(true);
    node.querySelector(".title").textContent = f.name;
    node.querySelector(".meta").textContent = `${fmtSize(f.size)}`;
    const a = node.querySelector("a.view");
    a.href = f.url; // откроется в новой вкладке
    const delBtn = node.querySelector("button.delete");
    delBtn.addEventListener("click", async () => {
      if (!confirm(`Удалить ${f.name}?`)) return;
      const r = await fetch(`/api/files/${encodeURIComponent(f.path)}`, { method: "DELETE" });
      if (r.ok) { node.remove(); } else { alert("Не удалось удалить"); }
    });
    fileList.appendChild(node);
  }
}

function fmtSize(n) {
  if (n == null) return "";
  const units = ["B","KB","MB","GB"]; let i=0; let v=n;
  while (v>=1024 && i<units.length-1) { v/=1024; i++; }
  return `${v.toFixed( (i===0)?0:1 )} ${units[i]}`;
}

refreshList();
