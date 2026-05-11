"""向量存储服务 - 支持系统共享库 + 用户私有库隔离"""
import os
import uuid
import gc
from datetime import datetime
from typing import Any, Callable

import numpy as np
import torch
from torch import Tensor
import faiss

from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.docstore.in_memory import InMemoryDocstore
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from sentence_transformers import SentenceTransformer

from server.config import settings
from server.utils.haodf_parser import parse_haodf_file, count_records


class STEmbeddings(Embeddings):
    """sentence-transformers 模型适配 LangChain Embeddings 接口"""

    def __init__(self, model_path: str, device: str = "cpu"):
        self._model: SentenceTransformer = SentenceTransformer(
            model_name_or_path=model_path, device=device
        )

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        with torch.no_grad():
            embs: Tensor = self._model.encode(texts, normalize_embeddings=True)
            return embs.tolist()

    def embed_query(self, text: str) -> list[float]:
        with torch.no_grad():
            return self._model.encode(text, normalize_embeddings=True).tolist()


class VectorStoreService:
    """向量数据库服务 - 系统共享库 + 用户私有库"""

    def __init__(self) -> None:
        self._embeddings: Any = None
        self._vectorstore: Any = None          # 系统共享 FAISS
        self._user_vectorstores: dict[str, Any] = {}  # 用户私有 FAISS
        self._documents: dict[str, dict[str, Any]] = {}

    # ========== 嵌入模型 ==========

    @property
    def embeddings(self) -> HuggingFaceEmbeddings | None:
        """获取嵌入模型"""
        if self._embeddings is not None:
            return self._embeddings

        if HuggingFaceEmbeddings:
            self._embeddings = HuggingFaceEmbeddings(
                model_name=settings.embedding_model_path,
                model_kwargs={"device": settings.embedding_device},
            )
        return self._embeddings

    # ========== 系统共享索引 ==========

    def _ensure_vectorstore(self):
        """确保系统向量存储已加载"""
        if self._vectorstore is None and FAISS:
            emb = self.embeddings
            if emb is None:
                return
            path: str = settings.vector_store_dir
            if os.path.exists(os.path.join(path, "index.faiss")):
                self._vectorstore = FAISS.load_local(
                    folder_path=path,
                    embeddings=emb,
                    allow_dangerous_deserialization=True,
                )
            else:
                emb = self.embeddings
                if emb is None:
                    return
                os.makedirs(name=path, exist_ok=True)
                self._vectorstore = FAISS.from_texts(
                    ["初始化文档"],
                    emb,
                    metadatas=[{"id": "init", "category": "system"}],
                )
                self._save()

    def _save(self):
        """保存系统向量存储"""
        if self._vectorstore:
            self._vectorstore.save_local(settings.vector_store_dir)

    async def search(
        self,
        query: str,
        top_k: int = 5,
        filter_category: str | None = None,
    ) -> list[dict[str, Any]]:
        """搜索系统共享向量库（好大夫医疗知识）"""
        self._ensure_vectorstore()
        if not self._vectorstore:
            return []
        kwargs: dict[str, Any] = {"k": top_k}
        if filter_category:
            kwargs["filter"] = {"category": filter_category}

        try:
            docs = self._vectorstore.similarity_search(query, **kwargs)
            return [
                {
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                    "score": 0.0,
                }
                for doc in docs
                if doc.page_content != "初始化文档"
            ]
        except Exception:
            return []

    # ========== 用户私有索引 ==========

    def _get_user_index_path(self, user_id: str) -> str:
        """获取用户向量库目录"""
        return os.path.join(settings.vector_store_dir, f"user_{user_id}")

    def _ensure_user_vectorstore(self, user_id: str):
        """确保用户私有向量库已加载"""
        if user_id in self._user_vectorstores:
            return
        emb = self.embeddings
        if emb is None:
            return
        path = self._get_user_index_path(user_id)
        index_path = os.path.join(path, "index.faiss")
        if os.path.exists(index_path):
            vs = FAISS.load_local(
                folder_path=path,
                embeddings=emb,
                allow_dangerous_deserialization=True,
            )
            self._user_vectorstores[user_id] = vs
        elif os.path.exists(path):
            vs = FAISS.from_texts(
                ["初始化用户记忆"],
                emb,
                metadatas=[{"id": "init", "category": "system", "user_id": user_id}],
            )
            vs.save_local(path)
            self._user_vectorstores[user_id] = vs

    async def search_user_index(
        self,
        user_id: str,
        query: str,
        top_k: int = 3,
        filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """搜索用户私有向量库（长期记忆），支持元数据过滤"""
        if not user_id:
            return []
        self._ensure_user_vectorstore(user_id)
        vs = self._user_vectorstores.get(user_id)
        if not vs:
            return []
        try:
            kwargs: dict[str, Any] = {"k": top_k}
            if filter:
                kwargs["filter"] = filter
            results = vs.similarity_search_with_score(query, **kwargs)
            return [
                {
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                    "score": float(score),
                }
                for doc, score in results
                if doc.page_content != "初始化用户记忆"
            ]
        except Exception:
            return []

    async def get_user_index_by_metadata(
        self,
        user_id: str,
        metadata_filter: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """根据元数据精确匹配检索用户私有向量库（不依赖语义相似度）"""
        if not user_id:
            return []
        self._ensure_user_vectorstore(user_id)
        vs = self._user_vectorstores.get(user_id)
        if not vs:
            return []
        try:
            # 迭代 docstore 中的所有文档，按元数据过滤
            matching: list[dict[str, Any]] = []
            for doc_id, doc in vs.docstore._dict.items():
                if doc.page_content == "初始化用户记忆":
                    continue
                match = True
                for key, value in metadata_filter.items():
                    if doc.metadata.get(key) != value:
                        match = False
                        break
                if match:
                    matching.append({
                        "content": doc.page_content,
                        "metadata": doc.metadata,
                        "doc_id": doc_id,
                    })
            # 按 turn_index 排序（如果有）
            matching.sort(key=lambda x: x["metadata"].get("turn_order", 0))
            return matching
        except Exception:
            return []

    async def add_to_user_index(
        self,
        user_id: str,
        texts: list[str],
        metadatas: list[dict[str, Any]] | None = None,
    ) -> bool:
        """向用户私有向量库添加文本（带相似度去重）"""
        if not user_id or not texts:
            return False
        self._ensure_user_vectorstore(user_id)
        vs = self._user_vectorstores.get(user_id)
        if not vs:
            return False
        try:
            # 为缺失 metadata 的文本补默认值
            if metadatas is None:
                metadatas = [{}] * len(texts)
            elif len(metadatas) < len(texts):
                metadatas += [{}] * (len(texts) - len(metadatas))

            # 相似度去重：跳过与已有记忆高度相似的内容
            texts_to_add: list[str] = []
            metadatas_to_add: list[dict[str, Any]] = []
            skipped = 0
            for i, text in enumerate(texts):
                try:
                    results = vs.similarity_search_with_score(text, k=1)
                    if results:
                        _, score = results[0]
                        # score 越小越相似（L2距离），归一化后判断
                        if score < 0.15:  # 非常相似，跳过
                            skipped += 1
                            continue
                except Exception:
                    pass
                texts_to_add.append(text)
                metadatas_to_add.append(metadatas[i])

            if not texts_to_add:
                return True  # 全部已存在，视为成功

            vs.add_texts(texts=texts_to_add, metadatas=metadatas_to_add)
            vs.save_local(self._get_user_index_path(user_id))
            return True
        except Exception:
            return False

    # ========== 文档管理（系统索引） ==========

    async def add_document(
        self,
        title: str,
        content: str,
        category: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """添加文档到系统索引"""
        self._ensure_vectorstore()
        doc_id = str(uuid.uuid4())
        meta: dict[str, Any] = {
            "id": doc_id,
            "title": title,
            "category": category or "general",
            "created_at": datetime.now().isoformat(),
            **(metadata or {}),
        }
        self._documents[doc_id] = {
            "title": title,
            "content": content,
            "metadata": meta,
        }
        if self._vectorstore and self.embeddings:
            self._vectorstore.add_texts(texts=[content], metadatas=[meta], ids=[doc_id])
            self._save()
        return doc_id

    async def delete_document(self, doc_id: str) -> bool:
        """从系统索引删除文档"""
        if doc_id not in self._documents:
            return False
        del self._documents[doc_id]
        if self._vectorstore:
            self._vectorstore.delete(ids=[doc_id])
            self._save()
        return True

    async def get_stats(self) -> dict[str, Any]:
        """获取系统向量库统计"""
        self._ensure_vectorstore()
        if not self._vectorstore:
            return {"total": 0, "status": "not_initialized"}
        try:
            total = self._vectorstore.index.ntotal
            return {"total": total, "status": "ok"}
        except Exception:
            return {"total": -1, "status": "unknown"}

    async def get_categories(self) -> list[str]:
        """获取系统索引所有分类"""
        categories = set()
        for doc in self._documents.values():
            cat = doc["metadata"].get("category")
            if cat:
                categories.add(cat)
        return list(categories)

    async def rebuild_index(self):
        """重建系统索引"""
        self._vectorstore = None
        self._ensure_vectorstore()
        for doc_id, doc in self._documents.items():
            if self._vectorstore:
                self._vectorstore.add_texts(
                    texts=[doc["content"]],
                    metadatas=[doc["metadata"]],
                    ids=[doc_id],
                )
        self._save()

    # ========== 好大夫批量导入（仅系统索引） ==========

    def batch_import_haodf_sync(
        self,
        file_path: str,
        batch_size: int = 64,
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> dict[str, int]:
        """
        流式批量导入好大夫医疗对话数据到系统索引
        """
        if not FAISS:
            raise RuntimeError("FAISS未初始化")

        total_records = count_records(file_path)
        if progress_callback:
            progress_callback(0, total_records, "parsing")

        st_model = SentenceTransformer(
            model_name_or_path=settings.embedding_model_path,
            device="cuda",
        )
        dim = st_model.get_embedding_dimension()
        assert dim is not None, "模型维度获取失败"

        cpu_index = faiss.index_factory(dim, "Flat", faiss.METRIC_INNER_PRODUCT)
        index = faiss.IndexIDMap(cpu_index)
        docstore_dict: dict[str, Document] = {}
        index_to_id: dict[int, str] = {}
        next_id = 0
        imported_count = 0
        skipped = 0

        with torch.no_grad():
            batch_texts: list[str] = []
            batch_metadatas: list[dict] = []

            for record in parse_haodf_file(file_path):
                content = record.get("content", "").strip()
                if not content:
                    skipped += 1
                    continue

                metadata = record.get("metadata", {})
                metadata["title"] = f"好大夫对话_{record['id']}"
                metadata["category"] = "haodf"
                metadata["id"] = f"haodf_{record['id']}"

                batch_texts.append(content)
                batch_metadatas.append(metadata)

                if len(batch_texts) >= batch_size:
                    self._process_batch(
                        st_model, dim, index, docstore_dict, index_to_id,
                        batch_texts, batch_metadatas, next_id,
                    )
                    next_id += len(batch_texts)
                    imported_count += len(batch_texts)
                    batch_texts.clear()
                    batch_metadatas.clear()
                    if progress_callback:
                        progress_callback(imported_count, total_records, "embedding")
                    gc.collect()
                    torch.cuda.empty_cache()

            if batch_texts:
                self._process_batch(
                    st_model, dim, index, docstore_dict, index_to_id,
                    batch_texts, batch_metadatas, next_id,
                )
                next_id += len(batch_texts)
                imported_count += len(batch_texts)

        if imported_count == 0:
            return {"total": total_records, "imported": 0, "skipped": total_records, "failed": 0}

        st_model.cpu()
        del st_model
        gc.collect()
        torch.cuda.empty_cache()

        if progress_callback:
            progress_callback(imported_count, total_records, "building_index")

        docstore = InMemoryDocstore(docstore_dict)
        self._query_embeddings = STEmbeddings(
            model_path=settings.embedding_model_path, device="cpu"
        )
        self._vectorstore = FAISS(
            embedding_function=self._query_embeddings,
            index=index,
            docstore=docstore,
            index_to_docstore_id=index_to_id,
        )
        self._save()

        if progress_callback:
            progress_callback(imported_count, total_records, "done")

        return {
            "total": total_records,
            "imported": imported_count,
            "skipped": skipped,
            "failed": total_records - imported_count - skipped,
        }

    def _process_batch(
        self,
        st_model: Any,
        dim: int,
        index: Any,
        docstore_dict: dict[str, Any],
        index_to_id: dict[int, str],
        texts: list[str],
        metadatas: list[dict],
        start_id: int,
    ) -> None:
        MAX_TEXT_LENGTH = 512
        texts = [t[:MAX_TEXT_LENGTH] for t in texts]

        try:
            batch_embeddings = st_model.encode(
                texts,
                show_progress_bar=False,
                normalize_embeddings=True,
                batch_size=min(32, len(texts)),
            )
        except Exception:
            batch_embeddings = np.zeros((len(texts), dim or 1024), dtype=np.float32)

        faiss_ids = np.arange(start_id, start_id + len(texts)).astype(np.int64)
        index.add_with_ids(
            np.ascontiguousarray(batch_embeddings, dtype=np.float32),
            faiss_ids,
        )

        for j, (text, meta) in enumerate(zip(texts, metadatas)):
            doc_id = str(start_id + j)
            docstore_dict[doc_id] = Document(page_content=text, metadata=meta)
            index_to_id[start_id + j] = doc_id

        del batch_embeddings, faiss_ids
        gc.collect()
        torch.cuda.empty_cache()


vector_store_service = VectorStoreService()
