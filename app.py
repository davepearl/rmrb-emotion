import pandas as pd
import streamlit as st

st.set_page_config(page_title="澎湃新闻情绪速览", layout="wide")
st.title("📰 澎湃新闻频道情绪速览")

# 尝试加载数据
try:
    df = pd.read_pickle("news.pkl")
    st.success(f"✅ 成功加载 {len(df)} 条新闻")
except FileNotFoundError:
    st.error("❌ 未找到 news.pkl 文件，请先运行爬虫")
    st.stop()

# 关键词搜索
keyword = st.text_input("搜索新闻标题（留空显示全部）", "")

# 情感筛选
sentiment_options = ["全部", "正面", "负面"]
selected_sentiment = st.selectbox("筛选情感", sentiment_options)

# 应用筛选
filtered_df = df.copy()
if keyword:
    filtered_df = filtered_df[filtered_df["title"].str.contains(keyword, na=False)]
if selected_sentiment != "全部":
    # 适配不同的标签格式
    if selected_sentiment == "正面":
        filtered_df = filtered_df[filtered_df["label"].str.upper().str.contains("POSITIVE|正面")]
    else:
        filtered_df = filtered_df[filtered_df["label"].str.upper().str.contains("NEGATIVE|负面")]

st.write(f"📊 显示 {len(filtered_df)} 条新闻")

# 显示新闻列表
for idx, row in filtered_df.iterrows():
    # 确定表情和标签显示
    if row.label in ['NEGATIVE', '负面', '负向'] or 'NEGATIVE' in str(row.label).upper():
        emoji = "🔴"
        label_text = "负面"
    else:
        emoji = "🟢"
        label_text = "正面"

    # 显示新闻
    with st.expander(f"{emoji} {row.title}"):
        st.write(f"**情感:** {label_text}")
        st.write(f"**时间:** {row.pub_time}")
        st.write(f"**置信度:** {row.score:.2%}")

        # 显示内容（限制长度）
        content = str(row.content)
        if len(content) > 500:
            content = content[:500] + "..."
        st.write(f"**内容:** {content}")

        # 显示原文链接（如果有）
        if 'url' in row:
            st.write(f"**原文链接:** [{row.url}]({row.url})")
