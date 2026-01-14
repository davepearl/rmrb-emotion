#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
澎湃新闻情感爬虫 – 2025 最终版（DOM 选择器版）
并发安全 | 一线程一浏览器 | 0 警告
"""
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

from selenium import webdriver
from selenium.webdriver.edge.service import Service
from bs4 import BeautifulSoup
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed

# ----------------  模型单例预热  -----------------
from model import predict_sentiment
predict_sentiment("预热")          # 主线程预热
# ------------------------------------------------

# ----------------  可配参数  --------------------
DRIVER_PATH   = r"D:\edgedriver_win64\msedgedriver.exe"
DOMAIN        = "www.thepaper.cn"
CHANNEL       = "channel_25950"
START_URL     = f"https://{DOMAIN}/{CHANNEL}"
SCROLL_BATCH  = 5
WAIT_SCROLL   = 1.5
MAX_ARTICLES  = 10
WORKERS       = 8         # 0=串行  >0=并发
SAVE_PATH     = "news.pkl"
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


# ----------- 线程独享 driver -----------
def _parse_one(url: str) -> Optional[Article]:
    options = webdriver.EdgeOptions()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--remote-debugging-port=0")   # 自动端口
    driver = webdriver.Edge(service=Service(DRIVER_PATH), options=options)
    try:
        driver.get(url)
        time.sleep(2)                                       # 等 JS 渲染
        soup = BeautifulSoup(driver.page_source, "html.parser")

        # ① 标题：优先 <h1>，其次 <title>，兜底 "无标题"
        title_tag = soup.find("h1") or soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else "无标题"

        # ② 发布时间：优先 <time>，其次含「20」的 span/div，兜底 1970
        time_tag = soup.find("time") or \
                   soup.find(lambda t: t.name in {"span", "div"} and
                                         t.get_text(strip=True) and
                                         "20" in t.get_text(strip=True))
        pub_time = time_tag.get_text(strip=True) if time_tag else "1970-01-01 00:00"

        # ③ 正文：所有 <p> 拼起来，统一洗白
        p_list = [p.get_text(strip=True) for p in soup.find_all("p")]
        content = "\n".join(p_list)
        content = html.unescape(content)                   # 反转义 \u003cp\u003e 等
        content = re.sub(r"<[^>]+>", "", content)          # 再保险去标签
        content = re.sub(r"\s+", " ", content).strip()     # 折叠多余空白
        content = unicodedata.normalize("NFKC", content)   # Unicode 正规化

        label, score = predict_sentiment(content)
        return Article(title, content, url, pub_time, label, float(score))
    except Exception as e:
        logging.warning("解析异常：%s —— %s", url, e)
        return None
    finally:
        driver.quit()


# ----------- 列表页滚动 + 收集链接（主线程） -----------
def _list_links() -> List[str]:
    options = webdriver.EdgeOptions()
    options.add_argument("--disable-blink-features=AutomationControlled")
    driver = webdriver.Edge(service=Service(DRIVER_PATH), options=options)

    driver.get(START_URL)
    time.sleep(2)
    for i in range(1, SCROLL_BATCH + 1):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(WAIT_SCROLL)
        logging.info("滚动进度 %s/%s", i, SCROLL_BATCH)

    soup = BeautifulSoup(driver.page_source, "html.parser")
    links = set()
    for a in soup.select("a[href]"):
        href = a["href"]
        if "newsDetail" not in href:
            continue
        if href.startswith("http"):
            links.add(href.split("?")[0])
        else:
            links.add(f"https://{DOMAIN}{href.split('?')[0]}")
    driver.quit()
    logging.info("解析到 %s 条详情链接", len(links))
    return list(links)


# ----------- 主入口 -----------
def main() -> None:
    links = _list_links()[:MAX_ARTICLES]
    if WORKERS <= 0:  # 串行
        articles = [_parse_one(u) for u in links]
        articles = [a for a in articles if a]
    else:  # 并发
        articles: List[Article] = []
        with ThreadPoolExecutor(max_workers=WORKERS) as exe:
            future_map = {exe.submit(_parse_one, u): u for u in links}
            for fut in as_completed(future_map):
                if art := fut.result():
                    articles.append(art)
                if len(articles) % 10 == 0:
                    logging.info("已抓取 %s 条", len(articles))

    df = pd.DataFrame([vars(a) for a in articles])
    df.to_pickle(SAVE_PATH)
    logging.info("✅ 已保存 %s 条到 %s", len(df), SAVE_PATH)


if __name__ == "__main__":
    main()