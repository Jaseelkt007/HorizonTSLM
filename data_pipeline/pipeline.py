import os
from pathlib import Path
import pandas as pd
from dotenv import load_dotenv

# 1. Resolve project root and load environment variables (including GEMINI_API_KEY)
root_dir = Path(__file__).resolve().parent.parent
dotenv_path = root_dir / ".env"
load_dotenv(dotenv_path)
api_key = os.getenv("GEMINI_API_KEY")

if api_key:
    print("GEMINI_API_KEY loaded successfully.\n")
else:
    print("Warning: GEMINI_API_KEY could not be loaded. Please check your .env file.\n")

# 2. Load the first 1000 rows of the SCADA CSV file
csv_path = root_dir / "data" / "Kelmarsh_SCADA_2016_3082" / "Turbine_Data_Kelmarsh_1_2016-01-03_-_2017-01-01_228.csv"

print(f"Loading data from: {csv_path}...")
df = pd.read_csv(csv_path, nrows=1000, skiprows=9)

# Clean up the first column name which might start with '# '
if df.columns[0].startswith('# '):
    df.rename(columns={df.columns[0]: df.columns[0][2:]}, inplace=True)


# 3. Print the first 5 rows to inspect column names
print("\n--- First 5 rows of the DataFrame ---")
print(df.head())
print("-" * 40)

# 4. Function to chunk the DataFrame into JSON strings
def chunk_to_json_list(dataframe: pd.DataFrame, chunk_size: int = 50) -> list[str]:
    """
    Splits a DataFrame into chunks of specified size and converts each chunk to a JSON string.
    """
    json_list = []
    # Iterate over the DataFrame in steps of chunk_size
    for start_idx in range(0, len(dataframe), chunk_size):
        chunk = dataframe.iloc[start_idx:start_idx + chunk_size]
        # orient="records" creates a list of dictionaries (one per row) in JSON
        json_list.append(chunk.to_json(orient="records"))
        
    return json_list

# Test the function
json_chunks = chunk_to_json_list(df, chunk_size=50)

print(f"\nThe DataFrame with {len(df)} rows was split into {len(json_chunks)} chunks (max 50 rows each).")
print("\nPreview of the first JSON chunk (first 200 characters):")
print(json_chunks[0][:200] + "...")
