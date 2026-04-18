import csv
import math

files = [
    '../prices_round_2_day_-1.csv',
    '../prices_round_2_day_0.csv',
    '../prices_round_2_day_1.csv'
]

osmium_prices = []
pepper_data = []  # tuples of (continuous_timestamp, mid_price)

# In Prosperity, timestamps typically run from 0 to 999,900 per day.
# To make them continuous across files, we add a day offset.
current_day = 0
for file in files:
    with open(file, 'r') as f:
        reader = csv.DictReader(f, delimiter=';')
        for row in reader:
            if not row['mid_price']: 
                continue
            
            mid_price = float(row['mid_price'])
            product = row['product']
            
            # Extract timestamp and add day offset
            # Assuming 1,000,000 max timestamps per day
            # Actually, "day" is given in the file (1, 0, -1)
            # Let's use the explicit day and assume 1M per day block
            day = int(row['day'])
            ts = float(row['timestamp'])
            continuous_ts = ts + (day * 1000000)
            
            if product == 'ASH_COATED_OSMIUM':
                osmium_prices.append(mid_price)
            elif product == 'INTARIAN_PEPPER_ROOT':
                pepper_data.append((continuous_ts, mid_price))

print("=== ASH COATED OSMIUM Analysis ===")
mean_osmium = sum(osmium_prices) / len(osmium_prices)
var_osmium = sum((p - mean_osmium)**2 for p in osmium_prices) / len(osmium_prices)
std_osmium = math.sqrt(var_osmium)
print(f"Mean Price: {mean_osmium:.2f}")
print(f"Standard Deviation: {std_osmium:.2f}")

print("\n=== INTARIAN PEPPER ROOT Analysis ===")
n = len(pepper_data)
sum_x = sum(d[0] for d in pepper_data)
sum_y = sum(d[1] for d in pepper_data)
sum_xy = sum(d[0]*d[1] for d in pepper_data)
sum_x2 = sum(d[0]**2 for d in pepper_data)

# Simple Linear Regression: slope m = (n*sum_xy - sum_x*sum_y) / (n*sum_x2 - sum_x**2)
denominator = (n * sum_x2 - sum_x**2)
if denominator == 0:
    print("Cannot compute slope, division by zero.")
    m = 0
else:
    m = (n * sum_xy - sum_x * sum_y) / denominator

b = (sum_y - m * sum_x) / n

print(f"Linear Trend (Slope per 1 timestamp): {m:.6f}")
print(f"Linear Trend (Slope per 1000 timestamp increments): {m * 1000:.6f}")
print(f"Intercept: {b:.2f}")

# Detrending to find noise
detrended = [y - m * x for x, y in pepper_data]
mean_detrended = sum(detrended) / len(detrended)
var_detrended = sum((d - mean_detrended)**2 for d in detrended) / len(detrended)
std_detrended = math.sqrt(var_detrended)

print(f"Detrended Mean Base Value: {mean_detrended:.2f}")
print(f"Detrended Standard Deviation: {std_detrended:.2f}")

print("\n=== Optimized Parameters ===")
print("ASH_COATED_OSMIUM -> Fair value:", round(mean_osmium))
print("INTARIAN_PEPPER_ROOT -> Alpha per 1k ticks:", round(m * 1000, 6))
print("INTARIAN_PEPPER_ROOT -> Base Fair Value Constant:", round(mean_detrended))
