# app/webui.py
from __future__ import annotations

import os
import hashlib
import logging
from pathlib import Path
from typing import List
from urllib.parse import unquote, quote

from aiohttp import web
import aiofiles

from config import settings
from opensearch_dir.opensearch_service import OpenSearchService
from app.database.requests import get_search_preview
import html

log = logging.getLogger(__name__)


def _safe_filename(name: str, max_bytes: int = 200) -> str:
    name = os.path.basename(name or "") or "uploaded.bin"
    base, ext = os.path.splitext(name)
    ext = ext[:20]
    if len(name.encode("utf-8")) <= max_bytes:
        return name

    digest = hashlib.sha1(name.encode("utf-8")).hexdigest()[:8]
    suffix = f"_{digest}"
    max_base_bytes = max_bytes - len((suffix + ext).encode("utf-8"))
    truncated = base
    while truncated and len(truncated.encode("utf-8")) > max_base_bytes:
        truncated = truncated[:-1]
    if not truncated:
        truncated = "file"
    return f"{truncated}{suffix}{ext}"


def _render_preview_page(query: str, items: List[dict]) -> str:
    cards: list[str] = []
    for item in items:
        title = html.escape(item.get("title") or item.get("filename") or "Документ")
        path = (item.get("path") or item.get("filename") or "").lstrip("/")
        snippet = item.get("snippet") or "(фрагмент недоступен)"
        snippet = snippet.replace("\n", "<br/>")
        download_url = f"/files/{quote(path)}"

        card = f"""
        <article class=\"result-card\">
            <h2>{title}</h2>
            <div class=\"result-body\">{snippet}</div>
            <div class=\"result-actions\">
                <a class=\"download\" href=\"{download_url}\" download>⬇️ Скачать файл</a>
            </div>
        </article>
        """
        cards.append(card)

    cards_html = "\n".join(cards) if cards else "<p>Совпадения не найдены.</p>"

    return f"""
    <!doctype html>
    <html lang=\"ru\">
    <head>
        <meta charset=\"utf-8\" />
        <title>Результаты поиска</title>
        <style>
            body {{
                font-family: 'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif;
                background: #0b0f13;
                color: #e5e7eb;
                margin: 0;
                padding: 0 16px 40px;
            }}
            header {{
                padding: 24px 0;
                text-align: center;
            }}
            h1 {{
                margin: 0;
                font-size: 28px;
            }}
            .query {{
                margin-top: 8px;
                color: #9ca3af;
                font-size: 16px;
            }}
            .results {{
                display: grid;
                gap: 20px;
                max-width: 960px;
                margin: 0 auto;
            }}
            .result-card {{
                background: #11161d;
                border-radius: 16px;
                padding: 20px;
                border: 1px solid #1f2937;
                box-shadow: 0 12px 24px rgba(0, 0, 0, 0.35);
            }}
            .result-card h2 {{
                margin: 0 0 12px;
                font-size: 20px;
                color: #f9fafb;
            }}
            .result-body {{
                max-height: 320px;
                overflow-y: auto;
                padding: 16px;
                background: rgba(15, 22, 33, 0.7);
                border-radius: 12px;
                border: 1px solid #1f2937;
                line-height: 1.5;
                color: #d1d5db;
            }}
            .result-body b {{
                color: #fcd34d;
            }}
            .result-actions {{
                margin-top: 16px;
                display: flex;
                justify-content: flex-end;
            }}
            .download {{
                display: inline-flex;
                align-items: center;
                gap: 8px;
                text-decoration: none;
                background: #2563eb;
                color: #fff;
                padding: 10px 18px;
                border-radius: 999px;
                font-weight: 600;
                transition: background 0.2s ease;
            }}
            .download:hover {{
                background: #1d4ed8;
            }}
            @media (max-width: 640px) {{
                body {{ padding: 0 12px 32px; }}
                .result-body {{ max-height: 260px; }}
            }}
        </style>
    </head>
    <body>
        <header>
            <h1>Результаты поиска</h1>
            <div class=\"query\">Запрос: {html.escape(query)}</div>
        </header>
        <section class=\"results\">
            {cards_html}
        </section>
    </body>
    </html>
    """

# Делаем обычную str, не bytes — чтобы поддерживалась кириллица
FALLBACK_INDEX: str = """<!doctype html>
<html lang="ru"><meta charset="utf-8"/>
<title>Файлы — drag & drop</title>
<style>
:root { --bg:#0b0f13; --panel:#11161d; --muted:#6b7280; --txt:#e5e7eb; --accent:#3b82f6; --ok:#10b981; --err:#ef4444; }
*{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--txt);font:16px/1.4 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
header{padding:16px 20px;border-bottom:1px solid #1f2937} h1{margin:0;font-size:20px}
main{padding:20px;max-width:1100px;margin:0 auto}
#uploader{background:var(--panel);border:1px solid #1f2937;padding:16px;border-radius:12px;margin-bottom:20px}
.dropzone{border:2px dashed #374151;border-radius:12px;padding:24px;text-align:center;background:#0d1218}
.dropzone.dragover{border-color:var(--accent);background:#0f1621}
.linklike{color:var(--accent);text-decoration:underline;cursor:pointer}
#fileInput{display:none}
#uploadBtn{margin-top:10px;padding:10px 16px;border-radius:10px;border:0;background:var(--accent);color:#fff;cursor:pointer}
#uploadBtn:disabled{opacity:.6;cursor:not-allowed}
.status{margin-top:8px;color:var(--muted);min-height:1.2em}
#files h2{margin:14px 0}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:12px}
.card{background:var(--panel);border:1px solid #1f2937;border-radius:12px;padding:12px}
.card .title{font-weight:600;margin-bottom:6px;word-break:break-all}
.card .meta{color:var(--muted);font-size:13px;margin-bottom:10px}
.actions{display:flex;gap:8px}
.actions a.view,.actions button.delete{font-size:14px;padding:8px 10px;border-radius:8px;border:1px solid #253142;background:#0f1621;color:var(--txt);text-decoration:none;cursor:pointer}
.actions a.view:hover{border-color:var(--accent)}
.actions button.delete{border-color:#3a2730}
.actions button.delete:hover{border-color:#ef4444;color:#fecaca}
</style>
<header><h1>Загрузка и управление файлами</h1></header>
<main>
  <section id="uploader">
    <div id="dropzone" class="dropzone">
      <p>Перетащите файлы сюда или <label for="fileInput" class="linklike">выберите</label></p>
      <input id="fileInput" type="file" multiple />
    </div>
    <button id="uploadBtn">Загрузить</button>
    <div id="uploadStatus" class="status"></div>
  </section>
  <section id="files">
    <h2>Файлы</h2>
    <div id="fileList" class="grid"></div>
  </section>
</main>
<template id="fileCardTpl">
  <div class="card">
    <div class="title"></div>
    <div class="meta"></div>
    <div class="actions">
      <a class="view" target="_blank" rel="noopener">Открыть</a>
      <button class="delete">Удалить</button>
    </div>
  </div>
</template>
<script>
const dropzone=document.getElementById("dropzone");
const fileInput=document.getElementById("fileInput");
const uploadBtn=document.getElementById("uploadBtn");
const statusEl=document.getElementById("uploadStatus");
const fileList=document.getElementById("fileList");
const tpl=document.getElementById("fileCardTpl");
let queue=[];
["dragenter","dragover"].forEach(evt=>dropzone.addEventListener(evt,e=>{e.preventDefault();e.stopPropagation();dropzone.classList.add("dragover");}));
["dragleave","drop"].forEach(evt=>dropzone.addEventListener(evt,e=>{e.preventDefault();e.stopPropagation();dropzone.classList.remove("dragover");}));
dropzone.addEventListener("drop",e=>{const files=Array.from(e.dataTransfer.files||[]);queue.push(...files);statusEl.textContent=`Выбрано файлов: ${queue.length}`;});
dropzone.addEventListener("click",()=>fileInput.click());
fileInput.addEventListener("change",e=>{const files=Array.from(e.target.files||[]);queue.push(...files);statusEl.textContent=`Выбрано файлов: ${queue.length}`;});
uploadBtn.addEventListener("click",async()=>{if(!queue.length){statusEl.textContent="Нет файлов для загрузки";return;}
 uploadBtn.disabled=true;try{const form=new FormData();for(const f of queue)form.append("file",f,f.name);
 const resp=await fetch("/api/upload",{method:"POST",body:form});if(!resp.ok)throw new Error("upload failed");
 const data=await resp.json();statusEl.textContent=`Загружено: ${data.saved.join(", ")}`;queue=[];await refreshList();}
 catch(e){console.error(e);statusEl.textContent="Ошибка загрузки";}finally{uploadBtn.disabled=false;fileInput.value="";}});
async function refreshList(){fileList.innerHTML="";const resp=await fetch("/api/files");const data=await resp.json();
 for(const f of data.files){const node=tpl.content.firstElementChild.cloneNode(true);
 node.querySelector(".title").textContent=f.name;node.querySelector(".meta").textContent=fmtSize(f.size);
 const a=node.querySelector("a.view");a.href=f.url;const delBtn=node.querySelector("button.delete");
 delBtn.addEventListener("click",async()=>{if(!confirm(`Удалить ${f.name}?`))return;const r=await fetch(`/api/files/${encodeURIComponent(f.path)}`,{method:"DELETE"});
 if(r.ok){node.remove();}else{alert("Не удалось удалить");}});fileList.appendChild(node);}}
function fmtSize(n){if(n==null)return"";const u=["B","KB","MB","GB"];let i=0,v=n;while(v>=1024&&i<u.length-1){v/=1024;i++;}return `${v.toFixed((i===0)?0:1)} ${u[i]}`;}
refreshList();
</script>
</html>
"""

def create_web_app(upload_dir: Path) -> web.Application:
    upload_dir.mkdir(parents=True, exist_ok=True)
    # Allow large uploads (e.g., 1.2GB). aiohttp default is much smaller.
    app = web.Application(client_max_size=1300 * 1024 ** 2)

    # Статика, если существует
    project_root = Path(__file__).resolve().parent.parent
    web_dir = project_root / "web"
    static_dir = web_dir / "static"
    if static_dir.exists():
        app.router.add_static("/static/", path=static_dir, name="static")

    async def index(_: web.Request) -> web.StreamResponse:
        idx = web_dir / "index.html"
        if idx.exists():
            return web.FileResponse(idx)
        return web.Response(text=FALLBACK_INDEX, content_type="text/html", charset="utf-8")

    app.router.add_get("/", index)

    async def list_files(_: web.Request) -> web.Response:
        items: List[dict] = []
        for p in sorted(upload_dir.rglob("*")):
            if p.is_file():
                rel = p.relative_to(upload_dir).as_posix()
                items.append({
                    "name": p.name,
                    "path": rel,
                    "size": p.stat().st_size,
                    "url": f"/files/{rel}",
                })
        return web.json_response({"files": items})

    app.router.add_get("/api/files", list_files)

    async def upload_file(request: web.Request) -> web.Response:
        reader = await request.multipart()
        saved: List[str] = []
        while True:
            part = await reader.next()
            if part is None:
                break
            if part.name != "file":
                continue
            max_bytes = 200
            filename = _safe_filename(part.filename or "uploaded.bin", max_bytes=max_bytes)
            dest = upload_dir / filename
            base, ext = os.path.splitext(filename)
            i = 1
            while dest.exists():
                filename = _safe_filename(f"{base} ({i}){ext}", max_bytes=max_bytes)
                dest = upload_dir / filename
                i += 1
            async with aiofiles.open(dest, "wb") as f:
                while True:
                    chunk = await part.read_chunk()
                    if not chunk:
                        break
                    await f.write(chunk)
            saved.append(filename)
            svc = OpenSearchService()
            res = svc.index_file(dest, refresh=True)

        return web.json_response({"saved": saved})

    app.router.add_post("/api/upload", upload_file)

    async def search_preview(request: web.Request) -> web.Response:
        token = request.match_info.get("token", "").strip()
        if not token:
            raise web.HTTPBadRequest(text="Missing token")

        preview = await get_search_preview(token)
        if not preview:
            raise web.HTTPNotFound(text="Preview not found")

        payload = preview.results or {}
        items = payload.get("results") if isinstance(payload, dict) else None
        if not isinstance(items, list):
            items = []

        page_html = _render_preview_page(preview.query_text, items)
        return web.Response(text=page_html, content_type="text/html", charset="utf-8")

    app.router.add_get("/search/{token}", search_preview)

    async def _extract_rel_path(request: web.Request) -> str:
        rel = None
        # 1) /api/files/{path:.*}
        if "path" in request.match_info:
            rel = request.match_info.get("path")
        # 2) ?path=...
        if not rel:
            rel = request.rel_url.query.get("path")
        # 3) JSON-формат { "path": "..." }
        if not rel and request.can_read_body:
            try:
                data = await request.json()
                rel = data.get("path")
            except Exception:
                pass
        if not rel:
            raise web.HTTPBadRequest(text="Missing 'path'")

        rel = unquote(rel).lstrip("/").replace("..", "")
        return rel

    async def delete_file(request: web.Request) -> web.Response:
        rel = await _extract_rel_path(request)
        # ✅ ИСПРАВЛЕНИЕ: используем upload_dir вместо UPLOAD_DIR
        target = (upload_dir / rel).resolve()

        # ✅ ИСПРАВЛЕНИЕ: используем upload_dir вместо UPLOAD_DIR
        if not str(target).startswith(str(upload_dir.resolve())):
            raise web.HTTPForbidden(text="Forbidden path")

        if not target.exists() or not target.is_file():
            raise web.HTTPNotFound(text="File not found")

        try:
            target.unlink()
        except Exception as e:
            log.exception("unlink failed for %s", target)
            raise web.HTTPInternalServerError(text=f"unlink error: {e}")

        idx_status = "ok"
        try:
            OpenSearchService().delete_by_path(rel)
        except Exception as e:
            log.warning("index cleanup failed for %s: %s", rel, e)
            idx_status = f"error: {e}"

        return web.json_response({"deleted": rel, "search_index": idx_status})

    app.router.add_delete("/api/files/{path:.*}", delete_file)

    async def serve_file(request: web.Request) -> web.StreamResponse:
        rel = request.match_info.get("path", "")
        rel = rel.replace("..", "").lstrip("/")
        target = (upload_dir / rel).resolve()
        if not str(target).startswith(str(upload_dir.resolve())):
            raise web.HTTPForbidden()
        if target.is_file() and target.exists():
            return web.FileResponse(target)
        raise web.HTTPNotFound(text="File not found")

    app.router.add_get("/files/{path:.*}", serve_file)

    return app
