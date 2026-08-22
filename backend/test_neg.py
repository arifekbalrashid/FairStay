import asyncio
import httpx

async def main():
    async with httpx.AsyncClient() as client:
        # Get properties
        r = await client.get("http://127.0.0.1:8000/api/properties")
        props = r.json()
        if not props:
            print("No properties found")
            return
        
        p_id = props[0]["id"]
        print(f"Starting negotiation for property {p_id}")
        
        # Start negotiation
        payload = {
            "party_a_preferences": {
                "hard_constraints": {"max_nightly_price": 4000, "min_stay_nights": 5},
                "soft_preferences": {"parking": True},
                "ideal_values": {"nightly_price": 3000, "stay_nights": 5, "total_price": 15000},
                "acceptable_values": {"nightly_price": 4000, "stay_nights": 5, "total_price": 20000},
                "priorities": ["nightly_price"],
                "negotiation_style": "moderate",
                "private_information": "Testing"
            }
        }
        r = await client.post(f"http://127.0.0.1:8000/api/properties/{p_id}/negotiate", json=payload)
        print("Response:", r.status_code, r.text)
        
        neg_id = r.json()["id"]
        print(f"Negotiation ID: {neg_id}")
        
        # Wait a bit for it to run
        await asyncio.sleep(2)
        
        # Check negotiation status
        r = await client.get(f"http://127.0.0.1:8000/api/negotiations/{neg_id}")
        print("Status:", r.status_code, r.json()["status"])
        if r.json()["status"] == "failed":
            print("Events:", r.json()["events"])

asyncio.run(main())
