import pandas as pd
import streamlit as st

st.set_page_config(page_title="澎湃新闻情绪速览", layout="wide")
st.title("📰 澎湃新闻频道情绪速览")

# 尝试加载数据
try:
    df = pd.read_pickle("news.pkl")
    st.success(f"✅ 成功加载 {len(df)} 条新闻")
    
    # 调试：显示标签的唯一值和类型
    with st.expander("🔍 调试信息"):
        st.write("📊 标签的唯一值:")
        st.write(df["label"].unique())
        st.write("📊 标签的数据类型:")
        st.write(df["label"].apply(type).unique())
        
except FileNotFoundError:
    st.error("❌ 未找到 news.pkl 文件，请先运行爬虫")
    st.stop()

# 关键词搜索
keyword = st.text_input("搜索新闻标题（留空显示全部）", "")

# 首先检查实际的标签值
unique_labels = df["label"].dropna().unique()
st.write(f"📝 数据中的标签类型: {unique_labels}")

# 创建情感筛选选项
sentiment_options = ["全部"]
if len(unique_labels) > 0:
    # 根据实际标签创建筛选选项
    for label in unique_labels:
        if isinstance(label, str):
            label_lower = label.lower()
            if "pos" in label_lower or "正面" in label_lower or "正" in label:
                sentiment_options.append("正面")
                break
    for label in unique_labels:
        if isinstance(label, str):
            label_lower = label.lower()
            if "neg" in label_lower or "负面" in label_lower or "负" in label:
                sentiment_options.append("负面")
                break

selected_sentiment = st.selectbox("筛选情感", sentiment_options)

# 应用筛选
filtered_df = df.copy()
if keyword:
    filtered_df = filtered_df[filtered_df["title"].str.contains(keyword, na=False)]

if selected_sentiment == "正面":
    # 匹配各种正面标签格式
    positive_patterns = ["POSITIVE", "positive", "正面", "正"]
    mask = False
    for pattern in positive_patterns:
        mask = mask | filtered_df["label"].astype(str).str.contains(pattern, case=False, na=False)
    filtered_df = filtered_df[mask]
elif selected_sentiment == "负面":
    # 匹配各种负面标签格式
    negative_patterns = ["NEGATIVE", "negative", "负面", "负"]
    mask = False
    for pattern in negative_patterns:
        mask = mask | filtered_df["label"].astype(str).str.contains(pattern, case=False, na=False)
    filtered_df = filtered_df[mask]

st.write(f"📊 显示 {len(filtered_df)} 条新闻")

# 如果筛选后没有数据，显示原始数据的前几行
if len(filtered_df) == 0:
    st.warning("⚠️ 筛选后无数据，显示前5条新闻")
    filtered_df = df.head(5)

# 显示新闻列表
for idx, row in filtered_df.iterrows():
    # 根据标签内容确定表情
    label_str = str(row.label).lower() if pd.notna(row.label) else ""
    
    if "neg" in label_str or "负面" in label_str or "负" in label_str:
        emoji = "🔴"
        label_text = "负面"
    elif "pos" in label_str or "正面" in label_str or "正" in label_str:
        emoji = "🟢"
        label_text = "正面"
    else:
        emoji = "⚪"
        label_text = f"未知({row.label})"
    
    # 显示新闻
    with st.expander(f"{emoji} {row.title}"):
        st.write(f"**情感标签:** {row.label}")
        st.write(f"**情感分类:** {label_text}")
        st.write(f"**时间:** {row.pub_time}")
        st.write(f"**置信度:** {row.score:.2%}")
        
        # 显示内容（限制长度）
        content = str(row.content) if pd.notna(row.content) else "无内容"
        if len(content) > 500:
            content = content[:500] + "..."
        st.write(f"**内容:** {content}")
        
        # 显示原文链接（如果有）
        if 'url' in row and pd.notna(row.url):
            st.write(f"**原文链接:** [{row.url}]({row.url})")
