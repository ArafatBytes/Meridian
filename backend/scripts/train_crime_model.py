import pandas as pd
import json
import os

# Define approximate center coordinates for Major Police Units
# This allows us to map a route's location to a regional risk score
UNIT_LOCATIONS = {
    "DMP": {"lat": 23.8103, "lon": 90.4125, "radius_km": 20},      # Dhaka Metro
    "CMP": {"lat": 22.3569, "lon": 91.7832, "radius_km": 15},      # Chittagong Metro
    "KMP": {"lat": 22.8456, "lon": 89.5403, "radius_km": 10},      # Khulna Metro
    "RMP": {"lat": 24.3636, "lon": 88.6241, "radius_km": 10},      # Rajshahi Metro
    "BMP": {"lat": 22.7010, "lon": 90.3535, "radius_km": 8},       # Barishal Metro
    "SMP": {"lat": 24.8949, "lon": 91.8687, "radius_km": 10},      # Sylhet Metro
    "RPMP": {"lat": 25.7439, "lon": 89.2752, "radius_km": 8},      # Rangpur Metro
    "GMP": {"lat": 23.9999, "lon": 90.4203, "radius_km": 15},      # Gazipur Metro
    # Ranges are larger areas - approximated centers
    "Dhaka Range": {"lat": 23.8103, "lon": 90.4125, "radius_km": 100},
    "Chittagong Range": {"lat": 22.3569, "lon": 91.7832, "radius_km": 100},
    "Khulna Range": {"lat": 22.8456, "lon": 89.5403, "radius_km": 80},
    "Rajshahi Range": {"lat": 24.3636, "lon": 88.6241, "radius_km": 80},
    "Barishal Range": {"lat": 22.7010, "lon": 90.3535, "radius_km": 60},
    "Sylhet Range": {"lat": 24.8949, "lon": 91.8687, "radius_km": 60},
    "Rangpur Range": {"lat": 25.7439, "lon": 89.2752, "radius_km": 60},
    "Mymensingh Range": {"lat": 24.7471, "lon": 90.4203, "radius_km": 60},
}

def train_model():
    csv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "backend", "bangladesh_crime_data_full.csv")
    if not os.path.exists(csv_path):
        print(f"Error: CSV file not found at {csv_path}")
        return

    print("Loading crime statistics...")
    df = pd.read_csv(csv_path)
    
    # Calculate Total Crimes per Unit across all time
    # Columns 1 to -1 are crime counts (Unit is 0, Date is last)
    crime_cols = df.columns[1:-1]
    
    # Ensure all crime columns are numeric (handle potential string issues)
    for col in crime_cols:
        try:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        except Exception as e:
            print(f"Warning: Could not convert column {col}: {e}")
            
    # Fill NaN values with 0
    df = df.fillna(0)
    
    # Group by Unit Name
    unit_stats = df.groupby("Names of Unit")[crime_cols].sum()
    
    # Calculate weighted severity score
    # Weights: Murder(10), Robbery(5), Rape/Repression(8), Theft(2), Others(1)
    # We map CSV columns to these weights roughly
    
    model_data = {}
    
    for unit in unit_stats.index:
        stats = unit_stats.loc[unit]
        
        # Calculate Weighted Risk Score
        # Adjust column names based on CSV headers
        score = (
            stats.get("Murder", 0) * 10 +
            stats.get("Dacoity", 0) * 8 +
            stats.get("Robbery", 0) * 6 +
            stats.get("Woman & Child Repression", 0) * 7 +
            stats.get("Kidnapping", 0) * 8 +
            stats.get("Burglary", 0) * 3 +
            stats.get("Theft", 0) * 2 +
            stats.get("Police Assault", 0) * 5 +
            stats.get("Riot", 0) * 4
        )
        
        # Normalize score (simple linear scaling relative to max possible or just raw score)
        # We'll keep raw score for now and normalize relative to all density later
        
        if unit in UNIT_LOCATIONS:
            model_data[unit] = {
                "risk_score": float(score),
                "location": UNIT_LOCATIONS[unit]
            }
            
    # Normalize scores 0-100 (where 100 is most dangerous region)
    max_score = max(d["risk_score"] for d in model_data.values()) if model_data else 1
    
    for unit in model_data:
        model_data[unit]["normalized_risk"] = (model_data[unit]["risk_score"] / max_score) * 100.0
        
    output_path = os.path.join(os.path.dirname(__file__), "crime_risk_model.json")
    with open(output_path, "w") as f:
        json.dump(model_data, f, indent=2)
        
    print(f"Model trained and saved to {output_path}")
    print("Top 5 Riskiest Regions:")
    sorted_risk = sorted(model_data.items(), key=lambda x: x[1]['normalized_risk'], reverse=True)
    for name, data in sorted_risk[:5]:
        print(f"  {name}: {data['normalized_risk']:.1f}")

if __name__ == "__main__":
    train_model()
