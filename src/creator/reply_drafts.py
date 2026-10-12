"""받은 댓글에 대한 작성자 답글 초안을 만든다.

OpenAI 키가 있으면 LLM으로 초안을 만들고, 없거나 실패하면 분류별 템플릿 초안을
돌려준다. 어느 쪽이든 초안일 뿐이며 게시는 작성자가 직접 고치고 승인해야 한다.
"""

from __future__ import annotations

import json

import requests

from src.llm.openai_client import (
    LLMGenerationError,
    OpenAIResponsesClient,
    _extract_json,
    _extract_output_text,
)
from src.recommender.safety_filter import get_block_reason

DRAFT_COUNT = 3
MAX_DRAFT_CHARS = 300

REPLY_INSTRUCTIONS = """당신은 YouTube 영상 작성자 본인이 시청자 댓글에 남길 답글 초안을 돕습니다.
규칙:
- 작성자 본인의 1인칭 목소리로, 정중한 해요체로 씁니다.
- 영상에 없는 사실, 일정, 약속(예: "다음 주에 올릴게요")을 지어내지 않습니다. 모르는 내용은 확인해 보겠다고 씁니다.
- 질문에는 답의 방향을 먼저 쓰고, 영상 정보만으로 답할 수 없으면 그렇다고 솔직하게 씁니다.
- 불만에는 방어하지 말고 인정할 부분을 인정한 뒤 개선 의지를 짧게 밝힙니다.
- 링크, 연락처, 구독·좋아요 요청을 넣지 않습니다.
- 각 초안은 1~3문장, 150자 이내로 씁니다.
반드시 JSON만 출력합니다: {"drafts": ["초안1", "초안2", "초안3"]}"""

TEMPLATES = {
    "question": [
        "좋은 질문 감사해요! 제가 한 번 더 확인해서 답글로 정리해 드릴게요.",
        "궁금하셨던 부분 남겨 주셔서 고마워요. 영상에서 충분히 설명하지 못한 것 같아 보충 설명을 준비해 볼게요.",
        "질문 감사합니다! 비슷한 궁금증이 있는 분들이 많을 것 같아 고정 댓글에도 같이 정리해 둘게요.",
    ],
    "complaint": [
        "솔직한 의견 감사해요. 말씀해 주신 부분은 다음 영상에서 개선해 볼게요.",
        "불편하셨던 점 남겨 주셔서 고마워요. 놓친 부분이 있었던 것 같아 꼼꼼히 다시 살펴보겠습니다.",
        "아쉬운 점 짚어 주셔서 감사합니다. 이런 피드백이 영상 만드는 데 정말 큰 도움이 돼요.",
    ],
    "praise": [
        "따뜻한 댓글 감사해요! 덕분에 다음 영상도 힘내서 만들 수 있을 것 같아요.",
        "재밌게 봐 주셔서 정말 고마워요. 앞으로도 도움이 되는 영상으로 찾아올게요!",
        "응원 감사합니다! 이런 댓글 하나하나가 큰 힘이 돼요.",
    ],
    "risk": [
        "의견 남겨 주셔서 감사해요. 말씀하신 내용은 사실관계를 확인한 뒤 정확하게 안내드릴게요.",
        "우려하시는 부분 이해해요. 확인 후 필요한 내용은 고정 댓글로 투명하게 공유하겠습니다.",
        "지적해 주셔서 감사합니다. 오해가 없도록 내용을 다시 점검해 볼게요.",
    ],
    "other": [
        "댓글 남겨 주셔서 감사해요!",
        "영상 봐 주셔서 고마워요. 앞으로도 자주 찾아와 주세요!",
        "의견 감사합니다. 다음 영상에도 참고할게요.",
    ],
}


def template_drafts(category: str) -> list[str]:
    return list(TEMPLATES.get(category, TEMPLATES["other"]))


def _clean_drafts(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    cleaned: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        draft = " ".join(value.split())
        if not draft or len(draft) > MAX_DRAFT_CHARS:
            continue
        if get_block_reason(draft) in {"profanity", "hate_speech", "threat", "spam"}:
            continue
        if draft not in cleaned:
            cleaned.append(draft)
    return cleaned[:DRAFT_COUNT]


def llm_drafts(client: OpenAIResponsesClient, *, comment: str, category: str, video_title: str | None) -> list[str]:
    client._ensure_ready()
    payload = {
        "model": client.model,
        "instructions": REPLY_INSTRUCTIONS,
        "input": json.dumps(
            {
                "video_title": video_title or "",
                "comment_category": category,
                "viewer_comment": comment,
                "draft_count": DRAFT_COUNT,
            },
            ensure_ascii=False,
        ),
        "max_output_tokens": 1200,
    }
    try:
        response = client.session.post(
            f"{client.base_url}/responses",
            headers={"Authorization": f"Bearer {client.api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=client.timeout,
        )
    except requests.RequestException as exc:
        raise LLMGenerationError("LLM API에 연결할 수 없습니다.") from exc
    if response.status_code < 200 or response.status_code >= 300:
        raise LLMGenerationError(f"LLM API 요청이 실패했습니다 ({response.status_code}).")
    try:
        output = _extract_output_text(response.json())
    except ValueError as exc:
        raise LLMGenerationError("LLM API 응답을 해석할 수 없습니다.") from exc
    parsed = _extract_json(output) if output else {}
    drafts = _clean_drafts(parsed.get("drafts") if isinstance(parsed, dict) else parsed)
    if not drafts:
        raise LLMGenerationError("사용할 수 있는 답글 초안이 없습니다.")
    return drafts


def draft_replies(
    *,
    comment: str,
    category: str,
    video_title: str | None = None,
    client: OpenAIResponsesClient | None = None,
) -> dict:
    if client is not None:
        try:
            return {"source": "llm", "drafts": llm_drafts(client, comment=comment, category=category, video_title=video_title)}
        except Exception:  # noqa: BLE001 - 초안은 템플릿으로 항상 돌려준다.
            pass
    return {"source": "template", "drafts": template_drafts(category)}
