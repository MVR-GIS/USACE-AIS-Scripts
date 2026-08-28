"""
FILE: arcgis_extractor.py
-------------------------
WHAT IT IS: 
    A reusable Python utility for extracting data from ArcGIS REST Feature Services.

PURPOSE:
    This script connects to an ArcGIS FeatureServer, handles the complexities of 
    pagination (fetching more than 1,000-2,000 records), flattens the JSON 
    response into a tabular format, and exports the result to a CSV file.

AUTHOR: 
    [Insert Name/Organization Here]
    Date: August 2024
-------------------------
"""

import requests
import pandas as pd
import urllib3

# Suppress insecure request warnings (common with internal USACE/Gov servers)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class ArcGISFeatureLoader:
    def __init__(self, base_url, verify_ssl=False):
        """
        :param base_url: The root URL of the FeatureServer (without the layer ID)
        :param verify_ssl: Set to False if using internal servers with self-signed certs
        """
        self.base_url = base_url.rstrip('/')
        self.verify_ssl = verify_ssl

    def fetch_layer(self, layer_id=0, where="1=1", out_fields="*", out_sr="4326"):
        """
        Fetches all records from a specific layer, handling pagination automatically.
        """
        query_url = f"{self.base_url}/{layer_id}/query"
        all_features = []
        offset = 0
        record_count_limit = 2000  # Standard ArcGIS limit

        print(f"--- Starting Data Extraction ---")
        print(f"Target Layer URL: {query_url}")

        while True:
            params = {
                'where': where,
                'outFields': out_fields,
                'f': 'json',
                'returnGeometry': 'true',
                'outSR': out_sr,
                'resultOffset': offset,
                'resultRecordCount': record_count_limit
            }

            try:
                response = requests.get(query_url, params=params, verify=self.verify_ssl)
                response.raise_for_status()
                data = response.json()

                # Check for ArcGIS-specific errors in the JSON response
                if "error" in data:
                    print(f"ArcGIS Server Error: {data['error'].get('message')}")
                    break

                features = data.get('features', [])
                if not features:
                    break

                all_features.extend(features)
                
                # If we retrieved fewer records than the limit, we've reached the end
                if len(features) < record_count_limit:
                    break
                
                offset += len(features)
                print(f"Progress: Downloaded {len(all_features)} records...")

            except Exception as e:
                print(f"Connection Error: {e}")
                break

        return self._process_json(all_features)

    def _process_json(self, features):
        """Flattens ArcGIS JSON structure into a clean list of dictionaries."""
        rows = []
        for f in features:
            attributes = f.get('attributes', {})
            geometry = f.get('geometry', {})

            # Extract Point Geometry (X/Y) if it exists
            if geometry:
                if 'x' in geometry:
                    attributes['longitude'] = geometry['x']
                    attributes['latitude'] = geometry['y']
                elif 'rings' in geometry:
                    attributes['geometry_type'] = 'Polygon'
            
            rows.append(attributes)
        
        return pd.DataFrame(rows)

# ==========================================
# PLUG AND PLAY CONFIGURATION
# ==========================================
if __name__ == "__main__":
    # 1. Set the Base URL (Everything up to /FeatureServer)
    SERVICE_URL = "https://emvrw07v05a0a05.mvr.ds.usace.army.mil/b5arcgis/rest/services/Transportation/MVR_Dredging_Layers/FeatureServer"
    
    # 2. Set the Layer ID (0, 1, 2, etc.)
    LAYER_ID = 0 
    
    # 3. Set the Output Filename
    OUTPUT_FILENAME = "MVR_Dredging_Export.csv"

    # --- Execution ---
    loader = ArcGISFeatureLoader(SERVICE_URL, verify_ssl=False)
    df = loader.fetch_layer(layer_id=LAYER_ID)

    if not df.empty:
        df.to_csv(OUTPUT_FILENAME, index=False)
        print(f"Success! Exported {len(df)} records to {OUTPUT_FILENAME}")
    else:
        print("No data was retrieved. Please check the Service URL and Layer ID.")