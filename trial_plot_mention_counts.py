"""
A Streamlit application visualizing weekly mentions of YouTube brands across a dataset.

This script analyzes brand mentions from YouTube within a specified date range and allows
users to interactively explore the data through plots and tables. It provides options
to view mentions by selected brands, as well as aggregated insights into related
channels and top brands.
"""

from pathlib import Path
import pandas as pd
import plotly.express as px
import streamlit as st

INPUT_PATH = Path("data/youtube_pivoted_brand_counts.csv")
COUNTS_INPUT = Path("data/youtube_brand_daily_counts.csv")  # must contain: date, keyword, video_mentions, top_channels
CHANNEL_WEEKLY_SUMMARY = Path("data/youtube_brand_channel_week_summary.csv")  # week_start, keyword, channel, channel_id, matched_videos, views, likeCount, commentCount, subscribers, channel_video_count

# Fallback: if weekly summary isn't under ./data, try ../data
if not CHANNEL_WEEKLY_SUMMARY.exists():
    alt = Path("../data/youtube_brand_channel_week_summary.csv")
    if alt.exists():
        CHANNEL_WEEKLY_SUMMARY = alt

START_DATE = '2025-08-28'
END_DATE = '2025-09-02'

st.set_page_config(page_title="Trial Brand Mentions (More than a Week)", layout='wide')

df = pd.read_csv(INPUT_PATH, encoding='utf-8')
df['date'] = pd.to_datetime(df['date'])
week = df[(df['date'] >= START_DATE) & (df['date'] <= END_DATE)].copy()

drop_cols = [c for c in ['date', 'total_mentions', 'num_brands_mentioned'] if c in week.columns]
brand_cols = [c for c in week.columns if c not in drop_cols]

# Also compute brand columns on the full dataset to allow "top 10 over entire period"
drop_cols_all = [c for c in ['date', 'total_mentions', 'num_brands_mentioned'] if c in df.columns]
brand_cols_all = [c for c in df.columns if c not in drop_cols_all]
week[brand_cols] = week[brand_cols].fillna(0)

st.title("YouTube Brand Mentions per Day (More than a Week)")
st.caption(f"Window: {START_DATE} -> {END_DATE}")

totals = week[brand_cols].sum().sort_values(ascending=False)
default_brands = list(totals.head(5).index)

selected = st.multiselect("Pick brands to plot",
                          options=brand_cols,
                          default=default_brands)

if not selected:
    st.info("Select at least one brand to display the plot.")
else:
    long_df = week[['date'] + selected].melt(id_vars="date", var_name='brand', value_name='mentions')
    fig = px.line(
        long_df,
        x='date',
        y='mentions',
        color='brand',
        markers=True,
        title='Daily Mentions for Selected Brands'
    )
    fig.update_layout(xaxis_title='Date', yaxis_title='Mentions', hovermode='x unified')
    st.plotly_chart(fig, use_container_width=True)


    with st.expander("Show data table"):
        st.dataframe(long_df.sort_values(["brand", "date"]).reset_index(drop=True))

# --- Top channels for selected brands by Reach & Engagement (weekly per-channel summary) ---
if selected and CHANNEL_WEEKLY_SUMMARY.exists():
    try:
        chw = pd.read_csv(CHANNEL_WEEKLY_SUMMARY, encoding='utf-8')
        need_cols = {"week_start", "keyword", "channel", "subscribers", "views", "likeCount", "commentCount"}
        if need_cols.issubset(set(chw.columns)):
            # parse dates
            # filter by window (overlap) & selected brands
            start_dt = pd.to_datetime(START_DATE)
            end_dt = pd.to_datetime(END_DATE)

            # Ensure week_start is datetime and synthesize week_end if missing (assume 7-day slices)
            chw["week_start"] = pd.to_datetime(chw["week_start"])  # start of each 7-day slice
            if "week_end" in chw.columns:
                chw["week_end"] = pd.to_datetime(chw["week_end"])
            else:
                chw["week_end"] = chw["week_start"] + pd.Timedelta(days=6)

            # Select rows whose weekly window overlaps the selected window
            overlaps = (chw["week_start"] <= end_dt) & (chw["week_end"] >= start_dt)
            mask = overlaps & (chw["keyword"].isin(selected))

            sub = chw.loc[mask, [
                "keyword", "channel", "subscribers", "views", "likeCount", "commentCount"
            ]].copy()

            # Coerce numerics (files can sometimes store counts as strings)
            for col in ["subscribers", "views", "likeCount", "commentCount"]:
                sub[col] = pd.to_numeric(sub[col], errors="coerce").fillna(0).astype(int)

            if not sub.empty:
                # Aggregate over possibly multiple weeks in the selected window
                agg = (sub.groupby(["keyword", "channel"], as_index=False)
                         .agg({
                             "subscribers": "max",   # channel-level attribute: take max observed
                             "views": "sum",
                             "likeCount": "sum",
                             "commentCount": "sum",
                         }))
                agg["engagement"] = agg["views"].fillna(0) + agg["likeCount"].fillna(0) + agg["commentCount"].fillna(0)

                # Top 3 by Reach (subscribers)
                top_reach = (agg.sort_values(["keyword", "subscribers"], ascending=[True, False])
                                .groupby("keyword").head(3).reset_index(drop=True))
                top_reach = top_reach.rename(columns={
                    "subscribers": "reach (subscribers)",
                    "views": "total views",
                    "likeCount": "total likes",
                    "commentCount": "total comments",
                })
                st.subheader("Top channels for selected brands (by reach: subscribers)")
                st.dataframe(top_reach, use_container_width=True)

                # Top 3 by Engagement (likes + views + comments)
                top_eng = (agg.sort_values(["keyword", "engagement"], ascending=[True, False])
                             .groupby("keyword").head(3).reset_index(drop=True))
                top_eng = top_eng.rename(columns={
                    "engagement": "total engagement (views+likes+comments)",
                    "views": "total views",
                    "likeCount": "total likes",
                    "commentCount": "total comments",
                })
                st.subheader("Top channels for selected brands (by engagement: views + likes + comments)")
                st.dataframe(top_eng[["keyword", "channel", "total engagement (views+likes+comments)", "total views", "total likes", "total comments"]], use_container_width=True)
            else:
                # Helpful hint: show what exists in the file to guide selection/window
                try:
                    min_w = chw["week_start"].min()
                    max_w = chw["week_end"].max() if "week_end" in chw.columns else (chw["week_start"].max() + pd.Timedelta(days=6))
                    brands_in_file = ", ".join(sorted(map(str, set(chw["keyword"].unique()))))
                    st.info(f"No weekly channel data after filtering. Available weeks: {min_w.date()} → {max_w.date()}. Brands present: {brands_in_file}.")
                except Exception:
                    st.info("No weekly channel data available for the selected window/brands.")
        else:
            st.info("Weekly channel summary missing required columns.")
    except Exception as e:
        st.warning(f"Could not load weekly channel summary: {e}")
else:
    if selected:
        st.caption("Tip: Run your YouTube collector so it produces 'data/youtube_brand_channel_week_summary.csv' to show Reach & Engagement tables.")

# --- Optional: Top 10 brands over the entire dataset, plotted over the selected week ---
st.markdown("---")
show_top10 = st.checkbox("Show Top 10 brands (by total mentions over entire dataset)", value=False)
if show_top10:
    totals_all = df[brand_cols_all].fillna(0).sum().sort_values(ascending=False)
    top10 = list(totals_all.head(10).index)

    if not top10:
        st.info("No brands available to compute Top 10.")
    else:
        st.subheader("Top 10 brands – weekly plot")
        top_week_long = week[["date"] + top10].melt(id_vars="date", var_name="brand", value_name="mentions")
        fig2 = px.line(
            top_week_long,
            x="date",
            y="mentions",
            color="brand",
            markers=True,
            title="Daily Mentions for Top 10 Brands (over entire dataset), within selected week"
        )
        fig2.update_layout(xaxis_title='Date', yaxis_title='Mentions', hovermode='x unified')
        st.plotly_chart(fig2, use_container_width=True)

        # Table: weekly totals for these Top 10
        week_totals = week[top10].fillna(0).sum().sort_values(ascending=False)
        week_totals_df = week_totals.rename("week_total_mentions").reset_index().rename(columns={"index": "brand"})
        st.subheader("Weekly totals for Top 10 brands")
        st.dataframe(week_totals_df, use_container_width=True)
