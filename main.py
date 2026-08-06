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
    """针对“生态、进化、保护与环境科学”进行深度筛选与翻译"""
    if not client:
        print("警告: 未检测到 LLM_API_KEY，跳过大模型筛选。")
        return None

    system_prompt = "你是一个专业科研助手，负责评估学术论文并严格按照指定的 JSON 格式返回数据。"
    
    user_prompt = f"""你是一名生态学、演化生物学、保护生物学与环境科学领域的专家。请分析以下发表在学术期刊《{journal_title}》上的论文信息：

标题：{title}
摘要：{summary}

请进行以下评估与处理：
1. 确定性分类：判断该研究是否属于“生态学（Ecology）、演化生物学/进化（Evolution）、保护生物学（Conservation Biology）或环境科学（Environmental Science）”相关的直接研究或重要交叉研究？
2. 中文翻译：将标题翻译为准确、专业的中文标题，并将英文摘要翻译为通顺专业的中文摘要。如果摘要信息较少，请依据现有信息精准总结。
3. 灵感与启发点：用 2-3 句话简要说明该研究的核心创新点及其对生态/进化/保护/环境科学领域的借鉴意义；若完全无关，填“无”。

必须严格按照以下 JSON 格式输出，不要包含任何 markdown 标记或其他文本：
{{
  "is_relevant": true或false,
  "relevance_score": 1到5的整数,
  "title_zh": "中文标题",
  "summary_zh": "中文摘要翻译",
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
            temperature=0.2
        )
        result_text = response.choices[0].message.content
        return json.loads(result_text)
    except Exception as e:
        print(f"调用 DeepSeek API 失败: {e}")
        return None

def generate_group_rss_feed(group_key, group_info, articles):
    """根据分组导出对应的 RSS 文件"""
    fg = FeedGenerator()
    fg.title(group_info['title'])
    fg.link(href='https://github.com/', rel='alternate')
    fg.description('基于 DeepSeek API 自动筛选的生态、进化、保护与环境科学顶级研究文献')
    fg.language('zh-CN')

    # 筛选出属于当前分组的文章
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
            
            content_html = f"""
            <p><strong>来源期刊：</strong> {art.get('source_journal', '未知期刊')}</p>
            <p><a href="{art['link']}">查看论文原文网页</a></p>
            <hr/>
            <h3>【英文原标题】</h3>
            <p>{art['title_en']}</p>
            <h3>【中文标题】</h3>
            <p>{art['title_zh']}</p>
            <hr/>
            <h3>【英文原文摘要】</h3>
            <p>{art['summary_en']}</p>
            <h3>【中文摘要翻译】</h3>
            <p>{art.get('summary_zh') or '暂无中文摘要'}</p>
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
