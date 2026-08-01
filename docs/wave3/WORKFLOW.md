# W3 Agent、门控执行与匿名反馈闭环

```text
Streamlit输入 → run_agent_turn → AgentTurnResult
→ Skills 1–2：理解与受控推断（最多一个问题）
→ Skill 3：硬约束过滤和推荐
→ Skills 4–5：文化内容与最终方案
→ 用户决定是否授权匿名记录
   ├─ 否：正常选品和下载，零持久化
   └─ 是：Skill 6 保存匿名会话、需求、推荐和最终动作
             → Skill 7 按产品、排名、场景、预算和轮数聚合
             → 人工解释并决定是否开展后续验证
```

Skill 7 不向客户公开、不读取聊天原文、不输出会话或事件 ID，也不修改 Skill 3 的硬约束、权重或排序。SQLite 供本地 Demo，PostgreSQL/Supabase 供未来跨实例存储；任一存储故障均在反馈分支内终止，不影响主流程。

需求修改会使旧推荐、选择、内容和方案失效。0结果不运行产品型 Skills 4/5；未选品不生成方案；完整状态机与安全 Trace 见 [ORCHESTRATION.md](ORCHESTRATION.md)。
