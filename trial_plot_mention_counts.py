"""
A Streamlit application visualizing weekly mentions of beauty brands across a dataset.

This script analyzes beauty brand mentions within a specified date range and allows
users to interactively explore the data through plots and tables. It provides options
to view mentions by selected brands, as well as aggregated insights into related
subreddits and top brands.

Attributes
----------
INPUT_PATH : pathlib.Path
    Path to the CSV file containing brand mentions data.
COUNTS_INPUT : pathlib.Path
    Path to the CSV file containing daily counts and subreddit information.
START_DATE : str
    Start date of the analysis window in 'YYYY-MM-DD' format.
END_DATE : str
    End date of the analysis window in 'YYYY-MM-DD' format.

Raises
------
Exception
    If an unexpected error occurs while loading or processing the 'COUNTS_INPUT' file.
"""

from pathlib import Path
import pandas as pd
import plotly.express as px
import streamlit as st

INPUT_PATH = Path("data/alias_pivoted_brand_counts.csv")
COUNTS_INPUT = Path("data/alias_brand_daily_counts.csv")  # must contain: date, keyword, post_mentions, top_subreddits
START_DATE = '2025-08-24'
END_DATE = '2025-08-31'

st.set_page_config(page_title="Beauty Brand Mentions (Weekly)", layout='wide')

df = pd.read_csv(INPUT_PATH, encoding='utf-8')
df['date'] = pd.to_datetime(df['date'])
week = df[(df['date'] >= START_DATE) & (df['date'] <= END_DATE)].copy()

drop_cols = [c for c in ['date', 'total_mentions', 'num_brands_mentioned'] if c in week.columns]
brand_cols = [c for c in week.columns if c not in drop_cols]

# Also compute brand columns on the full dataset to allow "top 10 over entire period"
drop_cols_all = [c for c in ['date', 'total_mentions', 'num_brands_mentioned'] if c in df.columns]
brand_cols_all = [c for c in df.columns if c not in drop_cols_all]
week[brand_cols] = week[brand_cols].fillna(0)

st.title("Beauty Brand Mentions per Day (Weekly)")
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

# --- Top subreddits for selected brands in the week ---
if COUNTS_INPUT.exists() and selected:
    try:
        df_counts = pd.read_csv(COUNTS_INPUT, encoding='utf-8')
        # Ensure columns exist
        required_cols = {"date", "keyword", "post_mentions", "top_subreddits"}
        if required_cols.issubset(set(df_counts.columns)):
            df_counts["date"] = pd.to_datetime(df_counts["date"])  # parse
            # filter by window & selection
            mask_counts = (
                (df_counts["date"] >= pd.to_datetime(START_DATE)) &
                (df_counts["date"] <= pd.to_datetime(END_DATE)) &
                (df_counts["keyword"].isin(selected))
            )
            sub = df_counts.loc[mask_counts, ["keyword", "top_subreddits", "post_mentions"]].copy()
            # split 'a;b;c' into rows; weight by post_mentions
            sub["top_subreddits"] = sub["top_subreddits"].fillna("")
            sub = sub.loc[sub["top_subreddits"] != ""]
            if not sub.empty:
                # explode into individual subreddit names
                sub = sub.assign(subreddit=sub["top_subreddits"].str.split(";"))
                sub = sub.explode("subreddit")
                sub["subreddit"] = sub["subreddit"].str.strip()
                # aggregate: sum post_mentions per (brand, subreddit)
                agg = (sub.groupby(["keyword", "subreddit"], as_index=False)["post_mentions"].sum()
                         .rename(columns={"post_mentions": "mentions"}))
                # take top 3 per brand
                top3 = (agg.sort_values(["keyword", "mentions"], ascending=[True, False])
                           .groupby("keyword")
                           .head(3)
                           .reset_index(drop=True))
                st.subheader("Top subreddits for selected brands (within window)")
                st.dataframe(top3, use_container_width=True)
            else:
                st.info("No subreddit info available for the selected window/brands.")
        else:
            st.info("Counts file found but missing required columns: date, keyword, post_mentions, top_subreddits")
    except Exception as e:
        st.warning(f"Could not load top subreddit info: {e}")
else:
    if not COUNTS_INPUT.exists():
        st.caption("Tip: Add 'data/brand_daily_counts.csv' (with 'top_subreddits') to show top subreddits here.")

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
