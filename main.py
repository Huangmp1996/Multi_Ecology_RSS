import json
import os
import feedparser
from openai import OpenAI
from feedgen.feed import FeedGenerator
from bs4 import BeautifulSoup
from datetime import datetime, timezone

# 分组定义订阅源列表
FEED_GROUPS = {
    # 第一组：Nature / Science 主刊
    "mainstream": {
        "title": "Top Journals - 生态/进化/保护/环境 灵感源",
        "file_name": "feed_mainstream.xml",
        "urls": [
            "https://www.nature.com/nature.rss",
            "https://www.science.org/action/showFeed?type=etoc&feed=rss&jc=science"
        ]
    },
    # 第二组：顶级子刊与综合期刊
    "specialized": {
        "title": "Sub-Journals & Multi-discipline - 生态/进化/保护/环境 灵感源",
        "file_name": "feed_specialized.xml",
        "urls": [
            "https://www.nature.com/nclimate.rss",
            "https://www.science.org/action/showFeed?type=etoc&feed=rss&jc=sciadv",
            "https://www.nature.com/ncomms.rss",
            "https://www.pnas.org/action/showFeed?type=searchTopic&taxonomyCode=type&tagCode=twip",
            "https://www.cell.com/current-biology/current.rss"
        ]
    }
}

HISTORY_FILE = "history.json"
OUTPUT_FILE = "processed_articles.json"

api_key = os.getenv("LLM_API_KEY")
base_url = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")

client = OpenAI(api_key=api_key, base_url=base_url) if api_key else None

def load_json(filepath, default):
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return default
    return default

def save_json(filepath, data):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def analyze_article_with_llm(title, summary, journal_title=""):
    """针对学术论文进行宏观生态与行为学垂直筛选，排除微进化与基因组学生理性研究"""
    if not client:
        print("警告: 未检测到 LLM_API_KEY，跳过大模型筛选。")
        return None

    system_prompt = (
        "你是一个深耕宏观生态学、群落生态学、生物地理学、动物行为学与保护生物学的资深学者。"
        "你的任务是筛选出关注中宏观生态学问题、表型适应或保护实践的论文，"
        "坚决剔除微进化、染色体进化、核型分析及单纯基因组学层面的研究，并严格返回 JSON 格式。"
    )
    
    user_prompt = f"""请分析以下发表在学术期刊《{journal_title}》上的论文信息：

标题：{title}
摘要：{summary}

【筛选规则与领域边界】

一、 【强制排除清单（直接判为无关，is_relevant 设为 false，评分为 1-2 分）】：
1. 基因组组装与结构变异：凡是核心内容为特定物种的染色体级别基因组组装（Genome assembly）、全基因组加倍（WGD）、核型进化（Karyotype evolution）、染色体重排/拓扑混合、异源多倍体起源等研究，一律排除。
2. 微进化与分子机制：基因位点关联（GWAS）、等位基因频率变异、转录组/单细胞测序、分子突变机制、DNA/RNA 生化通路等微观分子研究，一律排除。
3. 纯生物物理/细胞生物学：生物反应器、微流控、细胞动力学、蛋白质结构等。

二、 目标准入领域（仅当研究立足于个体、种群、群落、生态系统或生物地理等宏观/中观尺度）：
1. 宏观生态与群落构建：物种共存机制、功能性状、系统发育多样性、食物网、深度/纬度/环境梯度多样性格局。
2. 动物行为学与行为生态学：鸣声通讯/生物声学、群体决策、觅食与移动生态学、栖息地选择、表型适应。
3. 生物地理与宏观演化：大尺度物种多样性格局、区系划分、古气候/历史遗留效应、宏观物种分化与灭绝速率。
4. 全球变化与保护科学：气候变暖与人为干扰、生态系统弹性/转折点、保护优先区规划、监测技术（eDNA、水下视频、声学监测）。

三、 处理要求：
1. 确定性分类：严格依据上述规则判断，凡触及强制排除清单者一律判为 false。
2. 中文翻译：将标题翻译为准确、专业的中文标题；若英文摘要存在且包含实际内容，翻译为通顺专业的中文摘要；若无有效摘要或摘要过短，"summary_zh" 务必填空字符串 ""。
3. 灵感与启发点：若相关（is_relevant=true），用 2-3 句话指出该研究对宏观生态学/行为学/保护科学具体科学问题的明确价值；若判定为无关，填“无”。

必须严格按照以下 JSON 格式输出，不要包含任何 markdown 标记或其他文本：
{{
  "is_relevant": true或false,
  "relevance_score": 1到5的整数,
  "title_zh": "中文标题",
  "summary_zh": "中文摘要翻译（无摘要时务必填空字符串 \"\"）",
  "inspiration": "核心启发点与价值（中文）"
}}
"""

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.1  # 降低温度，确保模型严格遵守排除逻辑
        )
        result_text = response.choices[0].message.content
        return json.loads(result_text)
    except Exception as e:
        print(f"调用 DeepSeek API 失败: {e}")
        return None

def generate_group_rss_feed(group_key, group_info, articles):
    """根据分组导出对应的 RSS 文件（动态隐藏空白区块）"""
    fg = FeedGenerator()
    fg.title(group_info['title'])
    fg.link(href='https://github.com/', rel='alternate')
    fg.description('基于 DeepSeek API 自动筛选的生态、进化、保护与环境科学顶级研究文献')
    fg.language('zh-CN')

    group_articles = [a for a in articles if a.get('group') == group_key]

    if not group_articles:
        fe = fg.add_entry()
        fe.id(f'system-notice-empty-{group_key}')
        fe.title('【系统通知】订阅源运行正常，本次扫描未发现匹配文章')
        fe.link(href='https://github.com/')
        fe.description('系统已正常运行，本次未抓取到符合生态、进化、保护与环境科学标准的新研究。')
        fe.pubDate(datetime.now(timezone.utc))
    else:
        for art in group_articles:
            fe = fg.add_entry()
            fe.id(art['id'])
            fe.title(f"[{art['relevance_score']}分][{art.get('source_journal', '期刊')}] {art['title_zh']}")
            fe.link(href=art['link'])
            
            # 1. 构建头部信息
            content_html = f"""
            <p><strong>来源期刊：</strong> {art.get('source_journal', '未知期刊')}</p>
            <p><a href="{art['link']}">查看论文原文网页</a></p>
            <hr/>
            <h3>【英文原标题】</h3>
            <p>{art['title_en']}</p>
            <h3>【中文标题】</h3>
            <p>{art['title_zh']}</p>
            <hr/>
            """
            
            # 2. 只有当英文原文摘要不为空时，才显示【英文原文摘要】区块
            summary_en = art.get('summary_en', '').strip()
            if summary_en:
                content_html += f"<h3>【英文原文摘要】</h3><p>{summary_en}</p>"

            # 3. 只有当中文摘要翻译不为空时，才显示【中文摘要翻译】区块；无摘要时自动跳过
            summary_zh = art.get('summary_zh', '').strip()
            if summary_zh:
                content_html += f"<h3>【中文摘要翻译】</h3><p>{summary_zh}</p>"

            # 4. 追加末尾的启发与借鉴价值区块
            content_html += f"""
            <hr/>
            <h3>【生态/进化/环境借鉴价值与启发】</h3>
            <p><strong>相关度评分：</strong> {art['relevance_score']} / 5</p>
            <p>{art['inspiration']}</p>
            """
            
            fe.description(content_html)
            fe.pubDate(datetime.now(timezone.utc))

    output_filename = group_info['file_name']
    fg.rss_file(output_filename)
    print(f"成功生成分组 RSS 文件: {output_filename}")

def main():
    history = set(load_json(HISTORY_FILE, []))
    processed_articles = load_json(OUTPUT_FILE, [])
    new_filtered_articles = []

    # 遍历不同的组
    for group_key, group_info in FEED_GROUPS.items():
        print(f"\n==================== 开始处理分组: {group_key} ====================")
        for feed_url in group_info['urls']:
            print(f"\n---- 解析订阅源: {feed_url} ----")
            feed = feedparser.parse(feed_url)
            journal_title = getattr(feed.feed, 'title', 'Academic Journal')

            for entry in feed.entries:
                article_id = getattr(entry, 'id', entry.link)
                
                if article_id not in history:
                    title = entry.title
                    link = entry.link
                    
                    raw_summary = getattr(entry, 'description', getattr(entry, 'summary', ''))
                    clean_summary = ""
                    if raw_summary:
                        soup = BeautifulSoup(raw_summary, "html.parser")
                        clean_summary = soup.get_text(separator=' ', strip=True)

                    print(f"正在分析新文章: {title}")
                    
                    analysis = analyze_article_with_llm(title, clean_summary, journal_title)
                    
                    if analysis and analysis.get("is_relevant"):
                        article_data = {
                            "id": article_id,
                            "group": group_key,  # 标记所属分组
                            "source_journal": journal_title,
                            "title_en": title,
                            "title_zh": analysis.get("title_zh", title),
                            "summary_zh": analysis.get("summary_zh", ""),
                            "link": link,
                            "summary_en": clean_summary,
                            "relevance_score": analysis.get("relevance_score", 0),
                            "inspiration": analysis.get("inspiration", ""),
                            "published": getattr(entry, 'published', '')
                        }
                        new_filtered_articles.append(article_data)
                        print(f" -> [匹配成功] 得分: {analysis.get('relevance_score')} | 中文标题: {analysis.get('title_zh')}")
                    else:
                        print(" -> [过滤剔除] 判定与目标领域无关。")

                    history.add(article_id)

    if new_filtered_articles:
        processed_articles = (new_filtered_articles + processed_articles)[:200]
        save_json(OUTPUT_FILE, processed_articles)
        print(f"\n新增 {len(new_filtered_articles)} 篇符合要求的论文。")

    save_json(HISTORY_FILE, list(history))
    
    # 分别生成两个 XML 文件
    for group_key, group_info in FEED_GROUPS.items():
        generate_group_rss_feed(group_key, group_info, processed_articles)

if __name__ == "__main__":
    main()
