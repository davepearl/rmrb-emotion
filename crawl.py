#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
澎湃新闻情感爬虫 - GitHub Actions 适配版
在 GitHub Actions 虚拟机上运行，使用无头浏览器
"""
import os
import time
import random
import pickle
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional
import html
import re
import unicodedata

# 检查是否在 GitHub Actions 环境中
IS_GITHUB_ACTIONS = os.getenv('GITHUB_ACTIONS') == 'true'

# 根据环境选择不同的导入方式
if IS_GITHUB_ACTIONS:
    # GitHub Actions 环境：使用 Chrome 无头浏览器
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from webdriver_manager.chrome import ChromeDriverManager
else:
    # 本地环境：使用 Edge
    from selenium import webdriver
    from selenium.webdriver.edge.service import Service as EdgeService
    from selenium.webdriver.edge.options import Options as EdgeOptions

from bs4 import BeautifulSoup
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed

# ----------------  模型单例预热  -----------------
from model import predict_sentiment

predict_sentiment("预热")  # 主线程预热
# ------------------------------------------------

# ----------------  可配参数  --------------------
DOMAIN = "www.thepaper.cn"
CHANNEL = "channel_25950"
START_URL = f"https://{DOMAIN}/{CHANNEL}"
SCROLL_BATCH = 3  # 减少滚动次数，加快速度
WAIT_SCROLL = 1.0  # 缩短等待时间
MAX_ARTICLES = 5  # 减少文章数量，控制运行时间
WORKERS = 2 if IS_GITHUB_ACTIONS else 4  # GitHub Actions 减少并发数
SAVE_PATH = "news.pkl"
# -----------------------------------------------

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")


@dataclass
class Article:
    title: str
    content: str
    url: str
    pub_time: str
    label: str
    score: float


def _create_driver():
    """根据环境创建浏览器驱动"""
    if IS_GITHUB_ACTIONS:
        # GitHub Actions: 使用 Chrome 无头浏览器
        chrome_options = ChromeOptions()

        # 无头模式配置
        chrome_options.add_argument("--headless=new")  # 新版无头模式
        chrome_options.add_argument("--no-sandbox")  # 容器环境必需
        chrome_options.add_argument("--disable-dev-shm-usage")  # 共享内存限制
        chrome_options.add_argument("--disable-gpu")  # 虚拟机通常无GPU
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

        # 禁用图片加载，加快速度
        chrome_options.add_experimental_option(
            "prefs", {"profile.managed_default_content_settings.images": 2}
        )

        # 使用 webdriver-manager 自动管理驱动
        try:
            from webdriver_manager.chrome import ChromeDriverManager
            service = ChromeService(ChromeDriverManager().install())
        except ImportError:
            # 如果没有 webdriver-manager，尝试使用系统默认
            service = ChromeService()

        driver = webdriver.Chrome(service=service, options=chrome_options)

    else:
        # 本地环境：使用 Edge
        DRIVER_PATH = r"D:\edgedriver_win64\msedgedriver.exe"
        edge_options = EdgeOptions()
        edge_options.add_argument("--disable-blink-features=AutomationControlled")
        edge_options.add_argument("--remote-debugging-port=0")
        driver = webdriver.Edge(service=EdgeService(DRIVER_PATH), options=edge_options)

    return driver


def _parse_one(url: str) -> Optional[Article]:
    """解析单个文章页面"""
    driver = _create_driver()
    try:
        driver.get(url)
        time.sleep(2)  # 等待页面加载

        # 获取页面源代码
        html_content = driver.page_source

        # 如果页面内容过小，可能是加载失败
        if len(html_content) < 1000:
            logging.warning(f"页面内容过小，可能加载失败: {url}")
            return None

        soup = BeautifulSoup(html_content, "html.parser")

        # 提取标题
        title_tag = soup.find("h1") or soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else "无标题"

        # 提取发布时间
        time_tag = soup.find("time")
        if not time_tag:
            # 尝试其他可能的发布时间标签
            for tag in soup.find_all(["span", "div"]):
                text = tag.get_text(strip=True)
                if text and ("202" in text or "2023" in text or "2024" in text or "2025" in text):
                    time_tag = tag
                    break

        pub_time = time_tag.get_text(strip=True) if time_tag else "1970-01-01 00:00"

        # 提取正文内容
        content_parts = []

        # 尝试多种可能的正文选择器
        possible_selectors = [
            "article",
            ".news_txt",
            ".newscontent",
            ".article-content",
            "#articleContent",
            ".text"
        ]

        for selector in possible_selectors:
            elements = soup.select(selector)
            for elem in elements:
                paragraphs = elem.find_all("p")
                if paragraphs:
                    content_parts.extend([p.get_text(strip=True) for p in paragraphs])

        # 如果上述选择器都没找到，使用所有p标签
        if not content_parts:
            paragraphs = soup.find_all("p")
            content_parts = [p.get_text(strip=True) for p in paragraphs]

        # 清理内容
        content = "\n".join(content_parts)
        content = html.unescape(content)
        content = re.sub(r"<[^>]+>", "", content)
        content = re.sub(r"\s+", " ", content).strip()
        content = unicodedata.normalize("NFKC", content)

        # 内容过滤：去除过短或无效内容
        if len(content) < 50:
            logging.warning(f"内容过短: {title}")
            return None

        # 情感分析
        label, score = predict_sentiment(content)

        return Article(title, content, url, pub_time, label, float(score))

    except Exception as e:
        logging.warning(f"解析异常：{url} —— {str(e)[:100]}")
        return None
    finally:
        driver.quit()


def _list_links() -> List[str]:
    """获取文章链接列表"""
    driver = _create_driver()
    try:
        driver.get(START_URL)
        time.sleep(2)

        # 滚动加载更多内容
        for i in range(1, SCROLL_BATCH + 1):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(WAIT_SCROLL)
            logging.info(f"滚动进度 {i}/{SCROLL_BATCH}")

        # 获取页面源码
        soup = BeautifulSoup(driver.page_source, "html.parser")
        links = set()

        # 查找新闻链接
        for a in soup.find_all("a", href=True):
            href = a["href"]

            # 澎湃新闻的典型新闻链接模式
            if ("newsDetail" in href or
                    "/news_" in href or
                    re.search(r"/\d+$", href) or
                    re.search(r"/\d+_\d+", href)):

                # 规范化URL
                if href.startswith("http"):
                    full_url = href.split("?")[0]  # 去除查询参数
                elif href.startswith("//"):
                    full_url = f"https:{href.split('?')[0]}"
                elif href.startswith("/"):
                    full_url = f"https://{DOMAIN}{href.split('?')[0]}"
                else:
                    continue

                links.add(full_url)

        logging.info(f"解析到 {len(links)} 条详情链接")
        return list(links)

    except Exception as e:
        logging.error(f"获取链接列表失败: {e}")
        return []
    finally:
        driver.quit()


def main() -> None:
    """主函数"""
    # 设置模型下载镜像（如果需要）
    if IS_GITHUB_ACTIONS:
        import os
        os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
        logging.info("GitHub Actions 环境，使用 HF 镜像")

    # 获取链接
    links = _list_links()
    if not links:
        logging.error("未获取到任何链接")
        return

    # 限制文章数量
    links = links[:MAX_ARTICLES]
    logging.info(f"开始解析 {len(links)} 篇文章")

    # 解析文章
    articles = []

    if WORKERS <= 0 or IS_GITHUB_ACTIONS and WORKERS == 1:
        # 串行模式（GitHub Actions 建议串行，资源有限）
        for i, url in enumerate(links, 1):
            logging.info(f"正在解析第 {i}/{len(links)} 篇: {url[:50]}...")
            article = _parse_one(url)
            if article:
                articles.append(article)
                logging.info(f"✓ 已解析: {article.title[:30]}...")
    else:
        # 并发模式（本地环境使用）
        with ThreadPoolExecutor(max_workers=min(WORKERS, len(links))) as executor:
            future_to_url = {executor.submit(_parse_one, url): url for url in links}

            for i, future in enumerate(as_completed(future_to_url), 1):
                url = future_to_url[future]
                try:
                    article = future.result(timeout=60)  # 60秒超时
                    if article:
                        articles.append(article)
                        logging.info(f"✓ [{i}/{len(links)}] 已解析: {article.title[:30]}...")
                except Exception as e:
                    logging.warning(f"处理失败 {url}: {e}")

    # 保存结果
    if articles:
        df = pd.DataFrame([vars(a) for a in articles])
        df.to_pickle(SAVE_PATH)
        logging.info(f"✅ 已保存 {len(df)} 条到 {SAVE_PATH}")

        # 打印简要统计
        if not df.empty:
            logging.info("情感分布:")
            sentiment_counts = df['label'].value_counts()
            for label, count in sentiment_counts.items():
                logging.info(f"  {label}: {count} 篇")

            # 保存 CSV 以便查看
            csv_path = SAVE_PATH.replace('.pkl', '.csv')
            df.to_csv(csv_path, encoding='utf-8-sig', index=False)
            logging.info(f"📊 同时保存为 CSV: {csv_path}")
    else:
        logging.warning("未成功解析任何文章")


if __name__ == "__main__":
    main()
