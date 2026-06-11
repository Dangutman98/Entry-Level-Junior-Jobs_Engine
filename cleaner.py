import pandas as pd
import re

def clean_aggregators():
    try:
        df = pd.read_csv("relevant_jobs.csv", encoding="utf-8-sig")
        initial_count = len(df)
        
        # Define bad patterns in title or link
        bad_patterns = [
            r"jobs in",
            r"all .* jobs",
            r"search/",
            r"\?q=",
            r"results"
        ]
        
        # Filter rows
        def is_real_job(row):
            title = str(row.get('Job Title', '')).lower()
            link = str(row.get('Job Link', '')).lower()
            
            for p in bad_patterns:
                if re.search(p, title) or re.search(p, link):
                    return False
            return True
            
        mask = df.apply(is_real_job, axis=1)
        df_clean = df[mask]
        
        df_clean.to_csv("relevant_jobs.csv", index=False, encoding="utf-8-sig")
        final_count = len(df_clean)
        
        print(f"Cleaned CSV: Removed {initial_count - final_count} aggregator jobs. {final_count} real jobs remaining.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    clean_aggregators()
