import pandas as pd
import matplotlib.pyplot as plt
from wordcloud import WordCloud
import streamlit as st

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

# ===== 新增：一键情感词云 =====
def generate_wordcloud(df: pd.DataFrame):
    st.subheader("📊 情感词云")
    if st.button("一键生成词云"):
        # 分正面/负面
        pos_text = " ".join(df[df["label"] == "POSITIVE"]["content"])
        neg_text = " ".join(df[df["label"] == "NEGATIVE"]["content"])

        # 生成词云
        pos_cloud = WordCloud(width=400, height=300, background_color="white", colormap="Greens").generate(pos_text)
        neg_cloud = WordCloud(width=400, height=300, background_color="white", colormap="Reds").generate(neg_text)

        # 并排展示
        col1, col2 = st.columns(2)
        with col1:
            st.write("正面词云")
            fig1, ax1 = plt.subplots(figsize=(4, 3))
            ax1.imshow(pos_cloud, interpolation="bilinear")
            ax1.axis("off")
            st.pyplot(fig1)

        with col2:
            st.write("负面词云")
            fig2, ax2 = plt.subplots(figsize=(4, 3))
            ax2.imshow(neg_cloud, interpolation="bilinear")
            ax2.axis("off")
            st.pyplot(fig2)

# ===== 调用 =====
generate_wordcloud(df)
