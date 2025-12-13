from __future__ import annotations

import json

from pydantic_ai import RunContext

from minicc.core.models import MiniCCDeps, Question, QuestionOption, ToolResult


async def ask_user(ctx: RunContext[MiniCCDeps], questions: list[dict]) -> ToolResult:
    service = ctx.deps.ask_user_service
    if service is None:
        return ToolResult(success=False, output="", error="ask_user_service 未初始化")

    parsed_questions: list[Question] = []
    for q in questions:
        options = [
            QuestionOption(label=opt.get("label", ""), description=opt.get("description", ""))
            for opt in q.get("options", [])
        ]
        parsed_questions.append(
            Question(
                question=q.get("question", ""),
                header=q.get("header", ""),
                options=options,
                multi_select=q.get("multi_select", False),
            )
        )

    result = await service.ask(parsed_questions)
    return ToolResult(success=True, output=json.dumps(result.answers, ensure_ascii=False))

