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
START_DATE = '2025-08-28'
END_DATE = '2025-09-03'

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

# --- Top channels for selected brands in the week ---
if COUNTS_INPUT.exists() and selected:
    try:
        df_counts = pd.read_csv(COUNTS_INPUT, encoding='utf-8')
        # Ensure columns exist
        required_cols = {"date", "keyword", "video_mentions", "top_channels"}
        if required_cols.issubset(set(df_counts.columns)):
            df_counts["date"] = pd.to_datetime(df_counts["date"])  # parse
            # filter by window & selection
            mask_counts = (
                (df_counts["date"] >= pd.to_datetime(START_DATE)) &
                (df_counts["date"] <= pd.to_datetime(END_DATE)) &
                (df_counts["keyword"].isin(selected))
            )
            sub = df_counts.loc[mask_counts, ["keyword", "top_channels", "video_mentions"]].copy()
            # split 'a;b;c' into rows; weight by video_mentions
            sub["top_channels"] = sub["top_channels"].fillna("")
            sub = sub.loc[sub["top_channels"] != ""]
            if not sub.empty:
                # explode into individual channel names
                sub = sub.assign(channel=sub["top_channels"].str.split(";"))
                sub = sub.explode("channel")
                sub["channel"] = sub["channel"].str.strip()
                # aggregate: sum video_mentions per (brand, channel)
                agg = (sub.groupby(["keyword", "channel"], as_index=False)["video_mentions"].sum()
                         .rename(columns={"video_mentions": "mentions"}))
                # take top 3 per brand
                top3 = (agg.sort_values(["keyword", "mentions"], ascending=[True, False])
                           .groupby("keyword")
                           .head(3)
                           .reset_index(drop=True))
                st.subheader("Top channels for selected brands (within window)")
                st.dataframe(top3, use_container_width=True)
            else:
                st.info("No channel info available for the selected window/brands.")
        else:
            st.info("Counts file found but missing required columns: date, keyword, video_mentions, top_channels")
    except Exception as e:
        st.warning(f"Could not load top subreddit info: {e}")
else:
    if not COUNTS_INPUT.exists():
        st.caption("Tip: Add 'data/youtube_brand_daily_counts.csv' (with 'top_channels') to show top channels here.")

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
