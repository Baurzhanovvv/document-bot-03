from __future__ import annotations
import os, logging, re, html
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

import requests
from opensearchpy import OpenSearch, RequestsHttpConnection

log = logging.getLogger(__name__)


class OpenSearchService:
    """
    Сервис с автоматическими синонимами через synonym graph filter.
    Синонимы теперь встроены в анализатор и не требуют ручной настройки.
    """

    def __init__(self, index_name: Optional[str] = None) -> None:
        self.host = os.getenv("OPENSEARCH_HOST", "opensearch")
        self.port = int(os.getenv("OPENSEARCH_PORT", "9200"))
        self.scheme = os.getenv("OPENSEARCH_SCHEME", "http")
        self.user = os.getenv("OPENSEARCH_USER", "admin")
        self.password = os.getenv("OPENSEARCH_PASSWORD", "admin")
        self.index = index_name or os.getenv("OPENSEARCH_INDEX", "documents")
        self.use_ssl = os.getenv("OPENSEARCH_SSL", "0") in ("1", "true", "True")
        self.verify = os.getenv("OPENSEARCH_VERIFY", "0") in ("1", "true", "True")
        self._client: Optional[OpenSearch] = None

    def _get_synonyms_config(self) -> List[str]:
        """
        Автоматически генерируемые синонимы для русского и английского языков.
        Добавьте сюда базовые синонимы, которые будут работать автоматически.
        """
        return [
            # Документы и файлы
            "документ, файл, докумен, док",
            "договор, контракт, соглашение",
            "акт, документ",
            "счет, инвойс, invoice",
            "отчет, репорт, report",
            "справка, certificate",

            # Действия
            "поиск, найти, искать, search, find",
            "открыть, просмотреть, view, open",
            "скачать, загрузить, download",
            "удалить, стереть, delete, remove",

            # Организация
            "компания, организация, фирма, company, organization",
            "сотрудник, работник, employee, staff",
            "директор, руководитель, director, manager",

            # Даты и время
            "сегодня, today",
            "вчера, yesterday",
            "завтра, tomorrow",
            "месяц, month",
            "год, year",

            # Финансы
            "деньги, средства, money, funds",
            "оплата, платеж, payment",
            "стоимость, цена, price, cost",

            # Техника и IT
            "компьютер, пк, pc, computer",
            "программа, софт, software, program",
            "данные, информация, data, information",

            # Добавьте свои специфичные для вашей сферы синонимы
        ]

    def _get_client(self) -> Optional[OpenSearch]:
        if self._client is not None:
            return self._client
        try:
            client = OpenSearch(
                hosts=[{"host": self.host, "port": self.port, "scheme": self.scheme}],
                http_auth=(self.user, self.password),
                connection_class=RequestsHttpConnection,
                use_ssl=self.use_ssl,
                verify_certs=self.verify,
                ssl_assert_hostname=False,
                ssl_show_warn=False,
                timeout=10,
                max_retries=2,
                retry_on_timeout=True,
            )

            if not client.ping():
                log.warning("OpenSearch ping failed")
                return None

            # Создаём индекс с автоматическими синонимами
            self._ensure_index(client)
            self._client = client
            return client

        except Exception as e:
            log.warning("OpenSearch connect failed: %s", e)
            return None

    def _ensure_index(self, client: OpenSearch) -> None:
        """Создаёт индекс с настроенными synonym filters"""
        try:
            if client.indices.exists(index=self.index):
                log.info(f"Index {self.index} already exists")
                return

            # Получаем список синонимов
            synonyms = self._get_synonyms_config()

            body = {
                "settings": {
                    "index": {
                        "number_of_shards": 1,
                        "number_of_replicas": 0,
                    },
                    "analysis": {
                        "filter": {
                            # Русские стоп-слова и стемминг
                            "ru_stop": {
                                "type": "stop",
                                "stopwords": "_russian_"
                            },
                            "ru_stemmer": {
                                "type": "stemmer",
                                "language": "russian"
                            },

                            # Английские стоп-слова и стемминг
                            "en_stop": {
                                "type": "stop",
                                "stopwords": "_english_"
                            },
                            "en_stemmer": {
                                "type": "stemmer",
                                "language": "english"
                            },

                            # 🔥 АВТОМАТИЧЕСКИЕ СИНОНИМЫ
                            "synonym_filter": {
                                "type": "synonym_graph",
                                "synonyms": synonyms,
                                "updateable": True  # Можно обновлять без пересоздания индекса
                            },

                            # Фильтр для поискового анализатора (synonym в конце)
                            "synonym_filter_search": {
                                "type": "synonym_graph",
                                "synonyms": synonyms
                            }
                        },
                        "analyzer": {
                            # Анализатор для индексации (без синонимов при индексации)
                            "ruen_index": {
                                "type": "custom",
                                "tokenizer": "standard",
                                "filter": [
                                    "lowercase",
                                    "ru_stop",
                                    "ru_stemmer",
                                    "en_stop",
                                    "en_stemmer"
                                ]
                            },

                            # Анализатор для поиска (с синонимами)
                            "ruen_search": {
                                "type": "custom",
                                "tokenizer": "standard",
                                "filter": [
                                    "lowercase",
                                    "synonym_filter_search",  # Синонимы после lowercase
                                    "ru_stop",
                                    "ru_stemmer",
                                    "en_stop",
                                    "en_stemmer"
                                ]
                            }
                        }
                    }
                },
                "mappings": {
                    "properties": {
                        "path": {"type": "keyword"},
                        "filename": {
                            "type": "text",
                            "analyzer": "ruen_index",
                            "search_analyzer": "ruen_search",
                            "fields": {
                                "keyword": {"type": "keyword"}
                            }
                        },
                        "content": {
                            "type": "text",
                            "analyzer": "ruen_index",
                            "search_analyzer": "ruen_search"
                        },
                        "uploaded_at": {"type": "date"},
                        "size": {"type": "long"},
                        "mime": {"type": "keyword"},
                        "ext": {"type": "keyword"},
                        "content_indexed": {"type": "boolean"}
                    }
                }
            }

            client.indices.create(index=self.index, body=body)
            log.info(f"Created index {self.index} with automatic synonyms")

        except Exception as e:
            log.info(f"Index creation skipped: {e}")

    def update_synonyms(self, new_synonyms: List[str]) -> Dict[str, Any]:
        """
        Обновляет синонимы без пересоздания индекса (если нужно добавить через API).
        Это опциональный метод, если захотите добавить возможность обновления синонимов.
        """
        client = self._get_client()
        if not client:
            return {"error": "OpenSearch unavailable"}

        try:
            # Закрываем индекс
            client.indices.close(index=self.index)

            # Обновляем настройки синонимов
            body = {
                "analysis": {
                    "filter": {
                        "synonym_filter": {
                            "type": "synonym_graph",
                            "synonyms": new_synonyms,
                            "updateable": True
                        }
                    }
                }
            }

            client.indices.put_settings(index=self.index, body=body)

            # Открываем индекс
            client.indices.open(index=self.index)

            return {"ok": True, "message": f"Updated {len(new_synonyms)} synonym rules"}

        except Exception as e:
            log.error(f"Failed to update synonyms: {e}")
            # Пытаемся открыть индекс обратно
            try:
                client.indices.open(index=self.index)
            except:
                pass
            return {"error": str(e)}

    def _tika_url(self) -> str:
        u = os.getenv("TIKA_URL")
        if u:
            return u.rstrip("/") + "/tika"
        host = os.getenv("TIKA_HOST", "tika")
        port = os.getenv("TIKA_PORT", "9998")
        return f"http://{host}:{port}/tika"

    def index_file(self, file_path: Path, *, refresh: bool = True) -> Dict[str, Any]:
        client = self._get_client()
        if client is None:
            return {"skipped": "opensearch unavailable"}

        p = Path(file_path)
        if not p.exists() or not p.is_file():
            return {"error": "file not found"}

        base_dir = Path(os.getenv("UPLOAD_DIR", "/data/uploads")).resolve()
        try:
            rel = p.resolve().relative_to(base_dir)
        except Exception:
            rel = Path(p.name)

        content, content_indexed = "", False
        try:
            with open(p, "rb") as f:
                r = requests.put(
                    self._tika_url(),
                    data=f,
                    headers={"Accept": "text/plain; charset=UTF-8"},
                    timeout=120
                )
            r.raise_for_status()
            content = r.text or ""
            content_indexed = True
        except Exception as e:
            log.info("Tika extract failed (%s), indexing metadata only", e)

        doc = {
            "path": rel.as_posix(),
            "filename": p.name,
            "content": content,
            "uploaded_at": datetime.utcfromtimestamp(p.stat().st_mtime).isoformat(),
            "size": p.stat().st_size,
            "mime": self._guess_mime(p),
            "ext": p.suffix.lower().lstrip("."),
            "content_indexed": content_indexed,
        }

        try:
            client.index(index=self.index, body=doc, refresh=refresh)
            return {"ok": True, "path": doc["path"], "content_indexed": content_indexed}
        except Exception as e:
            log.warning("index error: %s", e)
            return {"error": str(e)}

    def delete_by_path(self, rel_path: str) -> Dict[str, Any]:
        client = self._get_client()
        if client is None:
            return {"skipped": "opensearch unavailable"}
        rel_path = (rel_path or "").strip().lstrip("/")
        query = {
            "bool": {
                "should": [
                    {"term": {"path.keyword": rel_path}},
                    {"prefix": {"path.keyword": rel_path.rstrip('/') + '/'}},
                ],
                "minimum_should_match": 1,
            }
        }
        try:
            resp = client.delete_by_query(
                index=self.index,
                body={"query": query},
                conflicts="proceed",
                refresh=True,
                ignore_unavailable=True,
            )
            return resp or {"ok": True}
        except Exception as e:
            log.warning("delete_by_query error: %s", e)
            return {"error": str(e)}

    def search(
            self,
            q: str | None = None,
            *,
            query: str | None = None,
            size: int | None = None,
            limit: int | None = None,
            offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Поиск с автоматическим применением синонимов.
        Синонимы теперь работают автоматически через search_analyzer.
        """
        q = (query if query is not None else q) or ""
        q = q.strip()
        n = size if size is not None else (limit if limit is not None else 5)

        if not q:
            return []

        client = self._get_client()
        if client is None:
            return []

        terms = [t for t in re.findall(r"\w+", q, flags=re.UNICODE) if t]
        content_query = q
        if len(terms) >= 2:
            content_query = terms[0]
            file_query = " ".join(terms[1:]).strip()
            # Поддерживаем оба порядка: "лечение гепатита" и "гепатит лечение".
            query_block = {
                "bool": {
                    "should": [
                        {
                            "bool": {
                                "must": [
                                    {
                                        "multi_match": {
                                            "query": file_query,
                                            "fields": [
                                                "filename^5",
                                                "path^2"
                                            ],
                                            "type": "best_fields",
                                            "operator": "AND",
                                            "fuzziness": "AUTO",
                                            "minimum_should_match": "75%"
                                        }
                                    },
                                    {
                                        "multi_match": {
                                            "query": content_query,
                                            "fields": ["content^3"],
                                            "type": "best_fields",
                                            "operator": "OR",
                                            "fuzziness": "AUTO",
                                            "minimum_should_match": "75%"
                                        }
                                    }
                                ]
                            }
                        },
                        {
                            "bool": {
                                "must": [
                                    {
                                        "multi_match": {
                                            "query": content_query,
                                            "fields": [
                                                "filename^5",
                                                "path^2"
                                            ],
                                            "type": "best_fields",
                                            "operator": "AND",
                                            "fuzziness": "AUTO",
                                            "minimum_should_match": "75%"
                                        }
                                    },
                                    {
                                        "multi_match": {
                                            "query": file_query,
                                            "fields": ["content^3"],
                                            "type": "best_fields",
                                            "operator": "OR",
                                            "fuzziness": "AUTO",
                                            "minimum_should_match": "75%"
                                        }
                                    }
                                ]
                            }
                        }
                    ],
                    "minimum_should_match": 1
                }
            }
        else:
            # Теперь используем простой multi_match - синонимы применяются автоматически
            query_block = {
                "multi_match": {
                    "query": q,
                    "fields": [
                        "filename^5",  # Имя файла важнее всего
                        "content^3",  # Содержимое тоже важно
                        "path^2"  # Путь менее важен
                    ],
                    "type": "best_fields",
                    "operator": "OR",  # Хотя бы одно слово должно совпасть
                    "fuzziness": "AUTO",  # Автоматическая коррекция опечаток
                    "minimum_should_match": "75%"  # Минимум 75% слов должны совпасть
                }
            }

        body = {
            "from": max(0, int(offset)),
            "size": n,
            "_source": ["filename", "path", "content", "content_indexed"],
            "query": query_block,
            "highlight": {
                "fields": {
                    "content": {
                        # Отдаём крупные фрагменты, чтобы затем вручную расширить их до 600+ символов
                        "fragment_size": 700,
                        "number_of_fragments": 5,
                    },
                    "filename": {}
                },
                # ✅ ИСПРАВЛЕНИЕ: используем <b> вместо <mark> для Telegram
                "pre_tags": ["<b>"],
                "post_tags": ["</b>"]
            }
        }

        try:
            resp = client.search(index=self.index, body=body, ignore_unavailable=True)
            hits = (resp.get("hits") or {}).get("hits") or []
        except Exception as e:
            log.warning("search error: %s", e)
            return []

        out: List[Dict[str, Any]] = []
        for h in hits:
            src = h.get("_source") or {}
            content = src.get("content") or ""

            # Используем highlight если есть, иначе делаем snippet
            highlight = h.get("highlight") or {}
            if "content" in highlight:
                snippet = self._make_extended_snippet(content, content_query, highlight["content"])
            else:
                snippet = self._make_extended_snippet(content, content_query)

            out.append({
                "filename": src.get("filename") or "Документ",
                "title": src.get("filename") or "Документ",
                "path": src.get("path") or "",
                "score": float(h.get("_score") or 0.0),
                "snippet": snippet,
            })
        return out

    @staticmethod
    def _sanitize_for_telegram(text: str) -> str:
        """
        Очищает HTML для Telegram, оставляя только поддерживаемые теги.
        Telegram поддерживает: <b>, <strong>, <i>, <em>, <u>, <ins>, <s>,
        <strike>, <del>, <code>, <pre>, <a>
        """
        # Заменяем неподдерживаемые теги на поддерживаемые
        text = text.replace("<mark>", "<b>").replace("</mark>", "</b>")
        text = text.replace("<span>", "").replace("</span>", "")
        text = text.replace("<div>", "").replace("</div>", "")

        # Экранируем специальные символы, которые не в тегах
        # (это базовая защита, для production лучше использовать библиотеку)
        return text

    @staticmethod
    def _make_extended_snippet(
        content: str,
        query: str,
        highlight_fragments: List[str] | None = None,
        *,
        before: int = 120,
        after: int = 620,
    ) -> str:
        """
        Формирует сниппет длиной > 600 символов для каждого найденного слова.

        Отдаём несколько фрагментов текста, каждый из которых содержит совпавшее
        слово, +600 символов после совпадения (и небольшой контекст до него).
        """

        if not content:
            return "(фрагмент недоступен)"

        # Нормализуем текст
        normalized = (
            content.replace("\r", " ").replace("\n", " ")
            if isinstance(content, str)
            else ""
        )
        normalized = re.sub(r"\s+", " ", normalized).strip()
        if not normalized:
            return "(фрагмент недоступен)"

        # Определяем термины запроса
        terms = [t for t in re.findall(r"\w+", query, flags=re.UNICODE) if t]
        if not terms and highlight_fragments:
            # fallback — извлекаем слова из highlight
            joined = " ".join(highlight_fragments)
            terms = [t for t in re.findall(r"\w+", joined, flags=re.UNICODE) if t]
        if not terms:
            terms = [normalized[:1]]

        unique_terms = []
        seen_terms = set()
        for term in terms:
            key = term.lower()
            if key not in seen_terms:
                seen_terms.add(key)
                unique_terms.append(term)

        fragments: List[str] = []
        used_ranges: list[tuple[int, int]] = []
        for term in unique_terms:
            pattern = re.compile(re.escape(term), flags=re.IGNORECASE)
            match = pattern.search(normalized)
            if not match:
                continue

            start = max(0, match.start() - before)
            end = min(len(normalized), match.end() + after)
            # Проверяем, что участок не пересекается с уже добавленными
            overlaps = any(not (end <= a or start >= b) for a, b in used_ranges)
            if overlaps:
                continue
            used_ranges.append((start, end))
            fragment = normalized[start:end]
            fragments.append(fragment)

        if not fragments:
            fragments = [normalized[: before + after]]

        # Готовим HTML с подсветкой совпавших слов
        highlighted: List[str] = []
        for fragment in fragments:
            escaped = html.escape(fragment, quote=False)
            for term in unique_terms:
                escaped_term = html.escape(term, quote=False)
                escaped = re.sub(
                    re.escape(escaped_term),
                    lambda m: f"<b>{m.group(0)}</b>",
                    escaped,
                    flags=re.IGNORECASE,
                )
            highlighted.append(escaped)

        snippet = "\n\n".join(highlighted)
        return snippet if snippet else "(фрагмент недоступен)"

    @staticmethod
    def _guess_mime(p: Path) -> str:
        ext = p.suffix.lower().lstrip(".")
        return {
            "pdf": "application/pdf",
            "doc": "application/msword",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "txt": "text/plain",
            "rtf": "application/rtf",
            "ppt": "application/vnd.ms-powerpoint",
            "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "xls": "application/vnd.ms-excel",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }.get(ext, "application/octet-stream")

    # @staticmethod
    # def _make_snippet(content: str, q: str, width: int = 600) -> str:
    #     if not content:
    #         return "(фрагмент недоступен)"
    #     txt = content.replace("\r", " ").replace("\n", " ")
    #     txt = re.sub(r"\s+", " ", txt).strip()
    #     if not q:
    #         return html.escape(txt[:width]) + ("…" if len(txt) > width else "")
    #
    #     terms = [t for t in re.findall(r"\w+", q, flags=re.UNICODE) if len(t) >= 3] or [q]
    #     pattern = re.compile("|".join(map(re.escape, terms)), re.IGNORECASE)
    #     m = pattern.search(txt)
    #     pos = m.start() if m else 0
    #     start = max(0, pos - width // 2)
    #     end = min(len(txt), start + width)
    #     frag = txt[start:end]
    #     if start > 0:
    #         frag = "…" + frag
    #     if end < len(txt):
    #         frag = frag + "…"
    #     return html.escape(frag)
    @staticmethod
    def _make_snippet(
            content: str,
            q: str,
            after_min: int = 70,
            after_max: int = 150,
            max_matches: int = 50,
    ) -> str:
        import re, html
        if not content:
            return "(фрагмент недоступен)"

        txt = re.sub(r"[ \t\f\v]+", " ", content.replace("\r", " ").replace("\n", " ")).strip()
        if not txt:
            return "(фрагмент недоступен)"
        if not q or not q.strip():
            end = min(len(txt), after_max)
            return html.escape(txt[:end] + (" …" if len(txt) > end else ""))

        terms = [t for t in re.split(r"\s+", q.strip()) if len(t) >= 2] or [q.strip()]
        low = txt.lower()
        spans = []

        for t in terms:
            pat = re.escape(t.lower())
            for m in re.finditer(pat, low, flags=re.IGNORECASE):
                s, e = m.start(), m.end()
                end_target = min(e + after_min, len(txt))
                hard_cap = min(e + after_max, len(txt))
                if end_target < hard_cap:
                    space_pos = txt.find(" ", end_target, hard_cap)
                    end_target = space_pos if space_pos != -1 else hard_cap
                else:
                    end_target = hard_cap
                spans.append((s, end_target))
                if len(spans) >= max_matches:
                    break
            if len(spans) >= max_matches:
                break

        if not spans:
            end = min(len(txt), after_max)
            return html.escape(txt[:end] + (" …" if len(txt) > end else ""))

        spans.sort()
        merged = []
        ms, me = spans[0]
        for s, e in spans[1:]:
            if s <= me:
                me = max(me, e)
            else:
                merged.append((ms, me))
                ms, me = s, e
        merged.append((ms, me))

        parts = []
        for s, e in merged:
            part = txt[s:e].strip()
            suffix = " …" if e < len(txt) else ""
            parts.append(part + suffix)
        if merged and merged[0][0] > 0:
            parts[0] = "… " + parts[0]
        return html.escape(" ".join(parts))
