import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Load dataset

df = pd.read_csv("data/agridata.csv")

print("Dataset loaded successfully.")
print("Shape:", df.shape)

# State-wise crop area
state_area = df.groupby("state")["area"].sum()

print("\nState-wise Crop Area:")
print(state_area)

# BAR CHART

plt.figure(figsize=(12, 6))

state_area.sort_values(ascending=False).plot(
    kind="bar"
)

plt.title("Total Crop Area by State")
plt.xlabel("State")
plt.ylabel("Total Crop Area")

plt.xticks(rotation=90)
plt.tight_layout()

plt.show()

# LINE CHART
plt.figure(figsize=(12, 6))

state_area.sort_index().plot(
    kind="line",
    marker="o"
)

plt.title("Crop Area by State")
plt.xlabel("State")
plt.ylabel("Total Crop Area")

plt.xticks(rotation=90)
plt.tight_layout()

plt.show()

# HEATMAP
state_crop_area = pd.pivot_table(
    df,
    values="area",
    index="state",
    columns="crop",
    aggfunc="sum"
)

plt.figure(figsize=(16, 10))

sns.heatmap(
    state_crop_area,
    cmap="YlGnBu"
)

plt.title("Crop Area by State and Crop")
plt.xlabel("Crop")
plt.ylabel("State")

plt.tight_layout()

plt.show()
