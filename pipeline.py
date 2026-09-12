import os
import pandas as pd
from dotenv import load_dotenv

# 1. Load environment variables (including GEMINI_API_KEY)
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if api_key:
    print("GEMINI_API_KEY wurde erfolgreich geladen.\n")
else:
    print("Warnung: GEMINI_API_KEY konnte nicht geladen werden. Bitte in .env überprüfen.\n")

# 2. Load the first 1000 rows of the SCADA CSV file
csv_path = r"C:\Users\benja\Desktop\Projekte\Hackathons\EHL_Zurich\zurich_ehl_timeseries\data\Kelmarsh_SCADA_2016_3082\Turbine_Data_Kelmarsh_1_2016-01-03_-_2017-01-01_228.csv"

print(f"Lade Daten von: {csv_path}...")
df = pd.read_csv(csv_path, nrows=1000, skiprows=9)

# Clean up the first column name which might start with '# '
if df.columns[0].startswith('# '):
    df.rename(columns={df.columns[0]: df.columns[0][2:]}, inplace=True)


# 3. Print the first 5 rows to inspect column names
print("\n--- Erste 5 Zeilen des DataFrames ---")
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

print(f"\nDer DataFrame mit {len(df)} Zeilen wurde in {len(json_chunks)} Chunks aufgeteilt (jeweils max 50 Zeilen).")
print("\nVorschau des ersten JSON-Chunks (erste 200 Zeichen):")
print(json_chunks[0][:200] + "...")
