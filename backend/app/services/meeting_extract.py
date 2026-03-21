"""
Meeting Transcript Conclusion Extractor

DB의 StepOutput에서 섹션별 최종 결론을 추출하여
Distill 프롬프트에 넣을 수 있는 구조화된 데이터를 생성한다.
"""
from __future__ import annotations

import re
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

STEP_LABELS = {
    "s1": "Campaign Goal",
    "s2": "Market Analysis",
    "s3": "Target Insight",
    "s4": "Principle Competition",
    "s5": "Target Definition",
    "s6": "Winning Strategy",
    "s7": "Consumer Promise",
    "s8": "Creative Strategy",
}


def extract_conclusions(project, step_outputs: dict) -> dict:
    """
    StepOutput 딕셔너리에서 섹션별 결론을 추출한다.

    Args:
        project: Project 모델 인스턴스
        step_outputs: {step_key: StepOutput} 딕셔너리

    Returns:
        {
            "meta": {"client": str, "project_date": str, "prepared_by": str},
            "sections": [...]
        }
    """
    meta = {
        "client": project.brand_name or "N/A",
        "project_date": (
            project.created_at.strftime("%Y.%m.%d")
            if isinstance(project.created_at, datetime)
            else str(project.created_at or "N/A")
        ),
        "prepared_by": "FLUX AI Strategy System",
    }

    sections = []
    for key in ["s1", "s2", "s3", "s4", "s5", "s6", "s7", "s8"]:
        step = step_outputs.get(key)
        if not step:
            continue

        # synthesis turn에서 결론 텍스트 추출
        conclusion_text = _get_synthesis_text(step)

        # 구조화된 결론 파싱
        premise = _extract_premise(conclusion_text)
        evidence = _extract_evidence(conclusion_text)
        direction = _extract_direction(conclusion_text)

        # lead analysis turn 추출 (보충 컨텍스트)
        lead_excerpt = _get_lead_analysis(step)

        sections.append({
            "section_id": key.upper(),
            "section_name": STEP_LABELS.get(key, key),
            "conclusion_text": conclusion_text,
            "premise": premise,
            "evidence": evidence,
            "direction": direction,
            "lead_analysis_excerpt": lead_excerpt,
        })

    return {"meta": meta, "sections": sections}


def build_distill_input(meta: dict, sections: list) -> str:
    """추출된 결론을 distill 프롬프트의 유저 메시지로 조합한다."""
    parts = []

    parts.append("## 프로젝트 정보")
    parts.append(f"- 클라이언트: {meta.get('client', 'N/A')}")
    parts.append(f"- 날짜: {meta.get('project_date', 'N/A')}")
    parts.append(f"- 작성: {meta.get('prepared_by', 'N/A')}")
    parts.append("")
    parts.append("## 섹션별 최종 결론")
    parts.append("")

    for section in sections:
        sid = section["section_id"]
        sname = section["section_name"]
        parts.append(f"### {sid}. {sname}")
        parts.append("")

        if section["premise"]:
            parts.append(f"**[전제]** {section['premise']}")
            parts.append("")

        if section["evidence"]:
            parts.append("**[근거]**")
            for j, ev in enumerate(section["evidence"], 1):
                parts.append(f"{j}. **{ev['title']}:** {ev['content']}")
            parts.append("")

        if section["direction"]:
            parts.append(f"**[결론 및 방향성]** {section['direction']}")
            parts.append("")

        # 구조화 파싱 실패 시 원문 결론 텍스트 포함
        if not section["premise"] and not section["evidence"]:
            text = section["conclusion_text"]
            if text:
                parts.append(text[:3000])
                parts.append("")

        parts.append("---")
        parts.append("")

    return "\n".join(parts)


# ──────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────

def _get_synthesis_text(step) -> str:
    """discussion_log에서 synthesis turn의 content를 추출."""
    logs = step.discussion_log or []
    for turn in reversed(logs):
        if isinstance(turn, dict) and turn.get("type") == "synthesis":
            return turn.get("content", "")
    # fallback: output_text
    return step.output_text or ""


def _get_lead_analysis(step) -> str:
    """discussion_log에서 lead의 analysis turn을 추출 (최대 2000자)."""
    logs = step.discussion_log or []
    for turn in logs:
        if (
            isinstance(turn, dict)
            and turn.get("role") == "lead"
            and turn.get("type") == "analysis"
        ):
            return (turn.get("content", ""))[:2000]
    return ""


def _extract_premise(text: str) -> str:
    """[전제] 블록 추출."""
    match = re.search(
        r"\*\*\[전제\]\*\*\n(.+?)(?=\n\*\*\[근거\]\*\*|\n\*\*\[결론)",
        text, re.DOTALL,
    )
    if match:
        return match.group(1).strip()

    # 볼드 없는 패턴도 시도
    match = re.search(
        r"\[전제\]\s*\n(.+?)(?=\n\[근거\]|\n\[결론)",
        text, re.DOTALL,
    )
    if match:
        return match.group(1).strip()

    return ""


def _extract_evidence(text: str) -> list[dict]:
    """[근거] 블록에서 번호 리스트 추출."""
    evidence = []
    pattern = re.compile(
        r"\d+\.\s+\*\*(.+?)\*\*[：:]\s*(.+?)(?=\n\d+\.\s+\*\*|\n\*\*\[결론|\Z)",
        re.DOTALL,
    )
    for match in pattern.finditer(text):
        evidence.append({
            "title": match.group(1).strip(),
            "content": match.group(2).strip(),
        })

    if not evidence:
        # 볼드 없는 패턴
        pattern2 = re.compile(
            r"\d+\.\s+(.+?)[：:]\s*(.+?)(?=\n\d+\.|\n\[결론|\Z)",
            re.DOTALL,
        )
        for match in pattern2.finditer(text):
            title = match.group(1).strip()
            content = match.group(2).strip()
            if len(title) < 50:  # 제목으로 보이는 경우만
                evidence.append({"title": title, "content": content})

    return evidence


def _extract_direction(text: str) -> str:
    """[결론 및 방향성] 블록 추출."""
    match = re.search(
        r"\*\*\[결론 및 (?:전략적 )?(?:방향성|실행 방향성)\]\*\*\n(.+?)(?=\n이 |\Z)",
        text, re.DOTALL,
    )
    if match:
        return match.group(1).strip()

    match = re.search(
        r"\[결론 및 (?:전략적 )?(?:방향성|실행 방향성)\]\s*\n(.+?)(?=\n이 |\Z)",
        text, re.DOTALL,
    )
    if match:
        return match.group(1).strip()

    return ""
