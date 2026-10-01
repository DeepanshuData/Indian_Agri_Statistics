import pandas as pd

try:
    df=pd.read_csv("Data/agridata.csv", on_bad_lines='skip')
    print("Data Loaded Successfully")
    
except FileNotFoundError:
    print("Error: The dataset file was not found.")
    exit()
    
except pd.errors.ParserError:
    print("Error: The csv file contains malformed rows.")
    exit()
    
print("\nOriginal rows :",len(df))    
    
print("\nMissing Values :")    
print(df.isnull().sum())

df_cleaned=df.dropna()
    
print("\nRows after cleaning :",len(df_cleaned))

df_cleaned.to_json(
    "output/cleaned_agriculture_data.json",
    orient="records",
    indent=4
)

print("\nCleaned data exported to JSON.")
