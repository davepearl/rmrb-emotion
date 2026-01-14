import streamlit as st
import pandas as pd

st.set_page_config(page_title="澎湃新闻情绪速览", layout="wide")
st.title("📰 澎湃新闻频道情绪速览")
st.caption("🔴负面  🟢正面/中性")

df = pd.read_pickle("news.pkl")

keyword = st.text_input("标题关键词过滤（留空显示全部）", "")
if keyword:
    df = df[df["title"].str.contains(keyword, na=False)]

for _, row in df.iterrows():
    emoji = "🔴" if row.label == "NEGATIVE" else "🟢"
    with st.expander(f"{emoji} {row.title}"):
        st.caption(f"{row.pub_time}  |  置信度：{row.score:.2f}")
        st.write(row.content[:400] + "…")