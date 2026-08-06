# Multidisciplinary Ecology & Environment Science RSS

本项目旨在解决综合性顶刊发文量大、学科跨度广导致文献追踪效率低的问题。系统利用 GitHub Actions 与 DeepSeek API 监控 Nature, Science, PNAS 等顶级综合期刊及顶级子刊，自动筛选并翻译属于“生态学、演化生物学、保护生物学与环境科学”领域的重点研究。

## 核心功能

* **多源分组订阅**：将综合性顶刊划分为“Nature/Science 主刊组”与“顶级子刊及综合大刊组”，各自生成独立的 RSS 订阅链接，方便分类阅读。
* **领域精准过滤**：深度评估论文是否属于生态学（Ecology）、演化生物学（Evolution）、保护生物学（Conservation）或环境科学（Environmental Science）领域。
* **双语提炼与动态排版**：生成中文标题、中文摘要翻译，并提炼核心创新点与借鉴意义。对于仅包含标题的 RSS 条目，自动隐藏摘要区块，不硬翻编造。
* **完全无服务器运维**：依托 GitHub 基础设施运行，零服务器成本，自动化运行与托管。

## 订阅源划分与目标期刊

* **分组 1：Top Journals（主刊源）**
  * *Nature*
  * *Science*
* **分组 2：Sub-Journals & Multi-discipline（子刊与综合大刊源）**
  * *Nature Climate Change*
  * *Science Advances*
  * *Nature Communications*
  * *PNAS*
  * *Current Biology*

## 实现路径

1. **分组迭代抓取（Group-based Ingestion）**：在 Python 脚本中按分组定义订阅源列表（`FEED_GROUPS`），通过 `feedparser` 依次获取各源条目，并记录 `group` 归属标签。
2. **LLM 领域认定（LLM Evaluation）**：使用 DeepSeek-V3 模型（`deepseek-chat`）对论文标题及摘要进行领域分类，严格过滤无关研究，仅保留生态/进化/环境高相关文献。
3. **多文件输出与部署（Multi-Feed Output）**：根据分组标签，利用 `feedgen` 分别导出 `feed_mainstream.xml` 与 `feed_specialized.xml`，通过 GitHub Actions 推送至 GitHub Pages 静态站点。

## 订阅链接

* **Nature / Science 主刊源**：
  `https://huangmp1996.github.io/Multi_Ecology_RSS/feed_mainstream.xml`
* **顶级子刊与综合大刊源**：
  `https://huangmp1996.github.io/Multi_Ecology_RSS/feed_specialized.xml`
