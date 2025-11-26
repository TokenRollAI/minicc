#!/usr/bin/env python3
"""
测试创建5个子Agent说Hi的脚本
"""

import asyncio
import os
from minicc import create_agent, load_config, MiniCCDeps


async def main():
    """创建5个子Agent并让它们说Hi"""
    
    # 加载配置
    print("正在加载配置...")
    config = load_config()
    print(f"使用模型: {config.provider.value}:{config.model}\n")
    
    # 创建主Agent
    agent = create_agent(config)
    deps = MiniCCDeps(
        config=config,
        cwd=os.getcwd()
    )
    
    # 创建任务：要求AI创建5个子Agent，每个都说Hi
    prompt = """请使用 spawn_agent 工具创建5个子Agent，让每个子Agent都说 "Hi"。
    
然后使用 get_agent_result 获取所有子Agent的结果。

注意：子Agent是异步执行的，需要等待一段时间后再获取结果。"""
    
    print("=" * 60)
    print("开始执行任务：创建5个子Agent说Hi")
    print("=" * 60)
    print()
    
    # 运行Agent（非流式）
    result = await agent.run(prompt, deps=deps)
    
    print("\n" + "=" * 60)
    print("任务完成！")
    print("=" * 60)
    print("\n最终响应：")
    print(result.data)
    
    # 显示子Agent状态
    print("\n" + "=" * 60)
    print(f"子Agent状态汇总（共 {len(deps.sub_agents)} 个）：")
    print("=" * 60)
    for task_id, task in deps.sub_agents.items():
        print(f"\n[{task_id}]")
        print(f"  状态: {task.status}")
        print(f"  任务: {task.prompt[:50]}...")
        if task.result:
            print(f"  结果: {task.result[:100]}...")


if __name__ == "__main__":
    asyncio.run(main())
