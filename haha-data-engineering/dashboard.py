"""Read only the atomically published catalog; no raw-event access in the UI."""
import json
from pathlib import Path
import sys
import pandas as pd
import streamlit as st
sys.path.insert(0, str(Path(__file__).resolve().parent))
from step07_daily_publish import digest

ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title="HAHA · 数据工程项目", layout="wide")
st.title("HAHA · 推荐流程分析")
st.caption("Spark 计算 · Airflow 调度 · 按业务日期发布")
st.info("全部为模拟数据，用于数据工程学习。选择行为不是订单，不代表真实用户或销售额。")
store = ROOT / "output/published"
if not (store / "catalog.json").exists():
    st.warning("尚无已发布数据，请先完成第七步任务。")
    st.stop()
catalog = json.loads((store / "catalog.json").read_text(encoding="utf-8"))
tables = {}
for day, entry in sorted(catalog["days"].items()):
    payload = json.loads((store / "versions" / (entry["version"] + ".json")).read_text(encoding="utf-8"))
    if digest(payload) != entry["version"]:
        st.error("发布文件校验失败，请重新检查数据。")
        st.stop()
    for name, rows in payload["tables"].items():
        tables.setdefault(name, []).extend(rows)
frames = {name: pd.DataFrame(rows) for name, rows in tables.items()}
overview = frames["ads_daily_overview"]
if overview.empty:
    st.warning("当前发布日期没有模拟事件。")
    st.stop()
days = sorted(overview.metric_date.unique())
selected = st.sidebar.slider("业务日期范围", min_value=pd.Timestamp(days[0]).date(),
    max_value=pd.Timestamp(days[-1]).date(), value=(pd.Timestamp(days[0]).date(), pd.Timestamp(days[-1]).date()))
for name, frame in frames.items():
    frames[name] = frame[(frame.metric_date >= str(selected[0])) & (frame.metric_date <= str(selected[1]))].copy()
overview = frames["ads_daily_overview"].sort_values("metric_date")
tab1, tab2, tab3 = st.tabs(["每日概览", "商品与场景", "工程验收"])
with tab1:
    totals = overview[["recommendation_count", "recommendation_item_count", "selection_count", "customization_brief_count"]].sum()
    columns = st.columns(4)
    for col, label, key in zip(columns, ["推荐次数", "展示商品数", "选择次数", "定制简报数"], totals.index):
        col.metric(label, f"{int(totals[key]):,}")
    if overview.is_window_complete.all() and totals.recommendation_count:
        st.metric("推荐转化率", f"{totals.selection_count / totals.recommendation_count:.2%}")
        st.caption("选择次数 ÷ 推荐次数；每次推荐展示 3 件商品，因此不同于商品选择率。")
    else:
        st.warning("部分日期尚未满足 73 小时观察窗口，暂不展示整体转化率。")
    st.line_chart(overview.set_index("metric_date")[["recommendation_count", "selection_count"]])
    st.dataframe(overview, hide_index=True)
    st.download_button("下载当前每日汇总", overview.to_csv(index=False).encode("utf-8-sig"), "haha_daily.csv")
with tab2:
    product = frames["dws_product_daily"].groupby("product_name_zh")[["recommendation_item_count", "selection_count"]].sum()
    st.subheader("商品选择次数")
    st.bar_chart(product.sort_values("selection_count", ascending=False).head(10)["selection_count"])
    st.caption("模拟选择有排名偏好；数量差异不能作为真实商品需求或因果结论。")
    st.subheader("场景与预算")
    scene = frames["ads_scene_budget_daily"].groupby(["scene", "budget_per_item_fen"])[["recommendation_count", "selection_count"]].sum().reset_index()
    scene["预算（元）"] = scene.budget_per_item_fen / 100
    st.dataframe(scene.drop(columns="budget_per_item_fen"), hide_index=True)
with tab3:
    st.write(f"当前发布 {len(catalog['days'])} 个业务日期；每个日期的三张汇总表一起切换版本。")
    st.caption("观察截止时间 as_of 是模拟时钟。73 小时 = 24 小时选择窗口 + 49 小时迟到容忍。")
    st.write("看板直接读取发布目录；点击右上角重新运行可刷新数据。")
    evidence = ROOT / "airflow/step07_verification.json"
    if evidence.exists():
        proof = json.loads(evidence.read_text())
        st.subheader("Airflow 验收记录（保存时的快照）")
        st.dataframe(pd.DataFrame(proof["runs"]), hide_index=True)
    benchmark = ROOT / "output/benchmark/results.json"
    if benchmark.exists():
        st.subheader("Spark 性能实验")
        st.dataframe(pd.DataFrame(json.loads(benchmark.read_text())["results"])[["rows", "query", "median_seconds", "checksum"]], hide_index=True)
        st.caption("本机 local[2]；每组预热一次、测量三次取中位数。缓存热态，结果不外推到生产集群。")
