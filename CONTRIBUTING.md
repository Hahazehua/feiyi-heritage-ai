# How to submit / 如何提交作品 — 数字文化赛道

## 中文

这是 SynNovator 平台上 **【S3W2复赛】全球青年培育赛** 活动的赛道仓库（track repository）。

**用途**：本仓库用来收集本赛道的所有参赛作品，并作为评委评审的代码基线。

**怎么提交作品**：
1. 在 web 页面上 **fork 本仓库**
2. 在你 fork 的版本里开发你的作品
3. 完成后，向 **本仓库** 发起 Pull Request
4. **回到 SynNovator 的活动页面，提交你的作品并填上 PR 链接**
   — 这一步会创建 submission 记录并触发索引更新
5. 之后你的提交会自动出现在 `SUBMISSIONS.md` 索引中

**仓库内容**：
- `SUBMISSIONS.md`——所有提交的索引（自动维护，请勿手动编辑）
- `submissions.json`——提交元数据（机器可读）
- `.forgejo/workflows/`——自动化工作流定义

---

## English

This is the track repository for the **【S3W2复赛】全球青年培育赛** event on SynNovator.

**Purpose**: This repo collects all submissions for this track and serves as
the code baseline for judges to review.

**How to submit**:
1. **Fork this repo** in the web UI
2. Develop your project in your fork
3. When done, open a **Pull Request back to this repo**
4. **Go back to the SynNovator event page and submit your work, pasting
   the PR URL** — this creates a submission record and triggers an index update
5. Your submission will then appear automatically in `SUBMISSIONS.md`

**What's in this repo**:
- `SUBMISSIONS.md` — auto-maintained index of all submissions (do not edit by hand)
- `submissions.json` — machine-readable submission metadata
- `.forgejo/workflows/` — automation workflow definitions
