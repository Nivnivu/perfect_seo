import time


def get_trends_data(keywords, timeframe="today 3-m", geo="IL"):
    """
    Get Google Trends data for keywords using pytrends.
    Returns dict with interest_over_time, rising_queries, top_queries.
    Handles pytrends being flaky - returns partial data on failure.
    """
    try:
        from pytrends.request import TrendReq
    except ImportError:
        print("  [trends] pytrends not installed, skipping trends data")
        return {"interest_over_time": {}, "rising_queries": {}, "top_queries": {}}

    result = {
        "interest_over_time": {},
        "rising_queries": {},
        "top_queries": {},
    }

    try:
        pytrends = TrendReq(hl="he-IL", tz=120)

        # pytrends accepts max 5 keywords at a time
        batches = [keywords[i:i + 5] for i in range(0, len(keywords), 5)]

        for batch in batches:
            try:
                pytrends.build_payload(batch, timeframe=timeframe, geo=geo)

                # Interest over time
                interest_df = pytrends.interest_over_time()
                if not interest_df.empty:
                    for kw in batch:
                        if kw in interest_df.columns:
                            values = []
                            for date, row in interest_df.iterrows():
                                values.append({
                                    "date": str(date.date()),
                                    "value": int(row[kw])
                                })
                            result["interest_over_time"][kw] = values

                # Related queries
                related = pytrends.related_queries()
                for kw in batch:
                    if kw in related:
                        # Rising queries
                        rising_df = related[kw].get("rising")
                        if rising_df is not None and not rising_df.empty:
                            result["rising_queries"][kw] = rising_df["query"].tolist()

                        # Top queries
                        top_df = related[kw].get("top")
                        if top_df is not None and not top_df.empty:
                            result["top_queries"][kw] = top_df["query"].tolist()

                time.sleep(2)
            except Exception as e:
                print(f"  [trends] Batch error for {batch}: {e}")
                continue

    except Exception as e:
        print(f"  [trends] Error: {e}")

    return result
