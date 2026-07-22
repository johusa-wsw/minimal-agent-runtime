from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from minimal_agent.tools.base import (
    BaseTool,
    ToolArguments,
    ToolContext,
    ToolExecutionError,
)


class SearchArguments(ToolArguments):
    query: str = Field(
        min_length=1,
        max_length=200,
        description="需要搜索的问题或关键词",
    )

    top_k: int = Field(
        default=3,
        ge=1,
        le=10,
        description="最多返回多少条搜索结果",
    )


class SearchDocument(BaseModel):
    id: str
    title: str
    content: str
    keywords: list[str] = Field(default_factory=list)


class SearchTool(BaseTool):
    name = "search"

    description = (
        "在本地模拟知识库中搜索资料。"
        "适合查询 Agent、Tool Calling、Session、Context 和 Memory 等概念。"
    )

    args_model = SearchArguments

    def __init__(
        self,
        data_path: str | Path = "data/mock_search.json",
    ) -> None:
        self._data_path = Path(data_path)
        self._documents: list[SearchDocument] | None = None

    def run(
        self,
        arguments: ToolArguments,
        context: ToolContext | None = None,
    ) -> dict[str, Any]:
        if not isinstance(arguments, SearchArguments):
            raise TypeError(
                "SearchTool received invalid argument type"
            )

        documents = self._load_documents()
        query = arguments.query.strip()

        scored_documents: list[
            tuple[int, SearchDocument]
        ] = []

        for document in documents:
            score = self._calculate_score(
                query=query,
                document=document,
            )

            if score > 0:
                scored_documents.append((score, document))

        scored_documents.sort(
            key=lambda item: (
                -item[0],
                item[1].title.casefold(),
            )
        )

        selected = scored_documents[: arguments.top_k]

        results = [
            {
                "id": document.id,
                "title": document.title,
                "snippet": self._make_snippet(
                    document.content
                ),
                "score": score,
            }
            for score, document in selected
        ]

        return {
            "query": query,
            "count": len(results),
            "results": results,
        }

    def _load_documents(self) -> list[SearchDocument]:
        if self._documents is not None:
            return self._documents

        if not self._data_path.exists():
            raise ToolExecutionError(
                f"Search data file does not exist: "
                f"{self._data_path}"
            )

        try:
            raw_data = json.loads(
                self._data_path.read_text(
                    encoding="utf-8"
                )
            )
        except json.JSONDecodeError as exc:
            raise ToolExecutionError(
                "Search data file is not valid JSON"
            ) from exc
        except OSError as exc:
            raise ToolExecutionError(
                f"Failed to read search data: {exc}"
            ) from exc

        if not isinstance(raw_data, list):
            raise ToolExecutionError(
                "Search data must be a JSON list"
            )

        try:
            self._documents = [
                SearchDocument.model_validate(item)
                for item in raw_data
            ]
        except Exception as exc:
            raise ToolExecutionError(
                f"Invalid search document: {exc}"
            ) from exc

        return self._documents

    @staticmethod
    def _calculate_score(
        query: str,
        document: SearchDocument,
    ) -> int:
        normalized_query = query.casefold()

        title = document.title.casefold()
        content = document.content.casefold()
        keywords = " ".join(
            document.keywords
        ).casefold()

        full_text = f"{title} {keywords} {content}"

        score = 0

        # 完整问题或短语直接命中，给予较高权重。
        if normalized_query in full_text:
            score += 20

        terms = SearchTool._extract_terms(
            normalized_query
        )

        for term in terms:
            score += title.count(term) * 5
            score += keywords.count(term) * 3
            score += content.count(term)

        return score

    @staticmethod
    def _extract_terms(query: str) -> set[str]:
        segments = re.findall(
            r"[a-z0-9_]+|[\u4e00-\u9fff]+",
            query,
        )

        terms: set[str] = set()

        for segment in segments:
            terms.add(segment)

            # 连续中文句子可能无法直接匹配，
            # 因此额外生成中文二元词组。
            if (
                re.fullmatch(
                    r"[\u4e00-\u9fff]+",
                    segment,
                )
                and len(segment) >= 3
            ):
                terms.update(
                    segment[index : index + 2]
                    for index in range(
                        len(segment) - 1
                    )
                )

        return {
            term
            for term in terms
            if term.strip()
        }

    @staticmethod
    def _make_snippet(
        content: str,
        max_length: int = 180,
    ) -> str:
        if len(content) <= max_length:
            return content

        return content[:max_length].rstrip() + "..."
