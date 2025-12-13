from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Callable
from uuid import uuid4

from pydantic_ai import Agent

from minicc.core.events import SubAgentCreated, SubAgentUpdated
from minicc.core.models import AgentTask, MiniCCDeps


@dataclass
class SubAgentService:
    deps: MiniCCDeps
    event_bus: Any
    agent_factory: Callable[[], Agent[MiniCCDeps, str]]

    async def run(
        self,
        *,
        prompt: str,
        description: str,
        subagent_type: str = "general-purpose",
        background: bool = False,
    ) -> tuple[str, str | None]:
        """
        运行子代理任务。

        - background=True：后台启动，立即返回 task_id。
        - background=False：等待执行完成后返回 (task_id, result)。
        """
        task_id = uuid4().hex[:8]
        task_obj = AgentTask(
            task_id=task_id,
            description=description,
            prompt=prompt,
            subagent_type=subagent_type,
            status="pending",
        )

        self.deps.sub_agents[task_id] = task_obj
        self.event_bus.emit(SubAgentCreated(task_id=task_id, description=description, prompt=prompt))
        self.event_bus.emit(SubAgentUpdated(task_id=task_id, status="pending"))

        if background:
            handle = asyncio.create_task(self._run(task_obj))
            self.deps.sub_agent_tasks[task_id] = handle
            return task_id, None

        await self._run(task_obj)
        return task_id, task_obj.result

    async def _run(self, task_obj: AgentTask) -> None:
        task_obj.status = "running"
        self.event_bus.emit(SubAgentUpdated(task_id=task_obj.task_id, status="running"))

        try:
            agent = self.agent_factory()
            result = await agent.run(task_obj.prompt, deps=self.deps)
            task_obj.status = "completed"
            task_obj.result = getattr(result, "output", str(result))
            self.event_bus.emit(
                SubAgentUpdated(task_id=task_obj.task_id, status="completed", result=task_obj.result)
            )
        except Exception as e:
            task_obj.status = "failed"
            task_obj.result = str(e)
            self.event_bus.emit(SubAgentUpdated(task_id=task_obj.task_id, status="failed", result=task_obj.result))
        finally:
            self.deps.sub_agent_tasks.pop(task_obj.task_id, None)
