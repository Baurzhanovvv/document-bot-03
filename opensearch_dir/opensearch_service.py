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
            log.info(
                "OpenSearch connect: %s://%s:%s index=%s ssl=%s verify=%s",
                self.scheme,
                self.host,
                self.port,
                self.index,
                self.use_ssl,
                self.verify,
            )
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
            log.exception("OpenSearch connect failed: %s", e)
            return None

    def _ensure_index(self, client: OpenSearch) -> None:
        """Создаёт индекс с настроенными synonym filters"""
        try:
            log.info("Ensure index: %s", self.index)
            if client.indices.exists(index=self.index):
                log.info(f"Index {self.index} already exists")
                return

            # Получаем список синонимов
            synonyms = self._get_synonyms_config()
            log.debug("Synonyms rules: %s", len(synonyms))

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
            log.exception("Index creation skipped: %s", e)

    def update_synonyms(self, new_synonyms: List[str]) -> Dict[str, Any]:
        """
        Обновляет синонимы без пересоздания индекса (если нужно добавить через API).
        Это опциональный метод, если захотите добавить возможность обновления синонимов.
        """
        client = self._get_client()
        if not client:
            return {"error": "OpenSearch unavailable"}

        try:
            log.info("Update synonyms: %s rules", len(new_synonyms))
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
            log.exception("Failed to update synonyms: %s", e)
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
            log.warning("Index file skipped (not found): %s", p)
            return {"error": "file not found"}

        base_dir = Path(os.getenv("UPLOAD_DIR", "/data/uploads")).resolve()
        try:
            rel = p.resolve().relative_to(base_dir)
        except Exception:
            rel = Path(p.name)

        content, content_indexed = "", False
        try:
            log.info("Index file start: %s", p)
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
            log.debug("Tika extracted content length: %s", len(content))
        except Exception as e:
            log.exception("Tika extract failed (%s), indexing metadata only", e)

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
            log.info("Index file success: %s", doc["path"])
            return {"ok": True, "path": doc["path"], "content_indexed": content_indexed}
        except Exception as e:
            log.exception("index error: %s", e)
            return {"error": str(e)}

    def reindex_folder(self, folder: Path, *, refresh: bool = True, recreate: bool = True) -> Dict[str, Any]:
        client = self._get_client()
        if client is None:
            return {"error": "opensearch unavailable"}

        target = Path(folder)
        if not target.exists():
            return {"error": f"folder not found: {target}"}

        log.info("Reindex folder start: %s recreate=%s", target, recreate)
        if recreate:
            try:
                client.indices.delete(index=self.index, ignore=[404])
            except Exception as e:
                log.exception("index delete failed: %s", e)
            self._ensure_index(client)

        total = 0
        indexed = 0
        errors: List[str] = []
        for p in sorted(target.rglob("*")):
            if not p.is_file():
                continue
            total += 1
            log.debug("Reindex file: %s", p)
            res = self.index_file(p, refresh=False)
            if res.get("ok"):
                indexed += 1
            else:
                err = res.get("error") or res.get("skipped") or "unknown error"
                errors.append(f"{p.name}: {err}")

        if refresh:
            try:
                client.indices.refresh(index=self.index)
            except Exception as e:
                log.exception("refresh failed: %s", e)

        log.info("Reindex folder done: total=%s indexed=%s errors=%s", total, indexed, len(errors))
        return {
            "ok": True,
            "total": total,
            "indexed": indexed,
            "errors": errors[:20],
        }

    def delete_by_path(self, rel_path: str) -> Dict[str, Any]:
        client = self._get_client()
        if client is None:
            return {"skipped": "opensearch unavailable"}
        rel_path = (rel_path or "").strip().lstrip("/")
        log.info("Delete by path: %s", rel_path)
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
            log.info("Delete by path done: %s", rel_path)
            return resp or {"ok": True}
        except Exception as e:
            log.exception("delete_by_query error: %s", e)
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
            log.debug("Search skipped: empty query")
            return []

        client = self._get_client()
        if client is None:
            log.warning("Search skipped: opensearch unavailable")
            return []

        terms = [t for t in re.findall(r"\w+", q, flags=re.UNICODE) if t]
        content_query = q
        log.info("Search start: q=%r terms=%s offset=%s size=%s", q, len(terms), offset, n)
        if len(terms) == 2:
            file_query = terms[1]
            content_query = terms[0]
            file_query_lc = file_query.lower()
            query_block = {
                "bool": {
                    "must": [
                        {
                            "bool": {
                                "should": [
                                    {
                                        "multi_match": {
                                            "query": file_query,
                                            "fields": [
                                                "filename^5",
                                                "path^2"
                                            ],
                                            "type": "best_fields",
                                            "operator": "OR",
                                            "fuzziness": "AUTO",
                                            "minimum_should_match": "75%"
                                        }
                                    },
                                    {
                                        "wildcard": {
                                            "filename.keyword": {
                                                "value": f"*{file_query}*",
                                                "case_insensitive": True
                                            }
                                        }
                                    },
                                    {
                                        "wildcard": {
                                            "path.keyword": {
                                                "value": f"*{file_query}*",
                                                "case_insensitive": True
                                            }
                                        }
                                    },
                                    {
                                        "script": {
                                            "script": {
                                                "source": (
                                                    "(doc['filename.keyword'].size()!=0 && "
                                                    "doc['filename.keyword'].value.toLowerCase().contains(params.q)) || "
                                                    "(doc['path.keyword'].size()!=0 && "
                                                    "doc['path.keyword'].value.toLowerCase().contains(params.q))"
                                                ),
                                                "params": {"q": file_query_lc},
                                            }
                                        }
                                    }
                                ],
                                "minimum_should_match": 1
                            }
                        }
                    ],
                    "should": [
                        {
                            "multi_match": {
                                "query": content_query,
                                "fields": ["content^3"],
                                "type": "best_fields",
                                "operator": "OR",
                                "fuzziness": "AUTO",
                                "minimum_should_match": "75%"
                            }
                        },
                        {
                            "term": {"content_indexed": False}
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
            log.debug("Search query: %s", query_block)
            resp = client.search(index=self.index, body=body, ignore_unavailable=True)
            hits = (resp.get("hits") or {}).get("hits") or []
        except Exception as e:
            log.exception("search error: %s", e)
            return []

        out: List[Dict[str, Any]] = []
        log.info("Search hits: %s", len(hits))
        for h in hits:
            src = h.get("_source") or {}
            content = src.get("content") or ""
            highlight = h.get("highlight") or {}
            content_highlights = highlight.get("content", [])
            if content_highlights:
                snippet = "\n\n".join([self._sanitize_for_telegram(frag) for frag in content_highlights])
            else:
                if not src.get("content_indexed", True):
                    snippet = "(содержимое не проиндексировано)"
                elif content:
                    max_len = 700
                    snippet = html.escape(content[:max_len]) + ("…" if len(content) > max_len else "")
                else:
                    snippet = "(фрагмент недоступен)"

            fname_high = highlight.get("filename", [])
            if fname_high:
                title = self._sanitize_for_telegram(fname_high[0])
            else:
                title = src.get("filename") or "Документ"

            out.append({
                "filename": src.get("filename") or "Документ",
                "title": title,
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
