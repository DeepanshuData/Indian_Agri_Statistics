from agri_function import (
    load_data,
    filter_by_area,
    filter_by_production,
    filter_by_crop,
    filter_by_state
)


df = load_data("data/agridata.csv")

area_data = filter_by_area(df, 50000)
print("Area > 50000:")
print(area_data.head(5))


production_data = filter_by_production(df, 100000)
print("\nProduction > 100000:")
print(production_data.head(5))


rice_data = filter_by_crop(df, "Rice")
print("\nRice records:")
print(rice_data.head(5))


andhra_data = filter_by_state(df, "ANDHRA PRADESH")
print("\nAndhra Pradesh records:")
print(andhra_data.head(5))