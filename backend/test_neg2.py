import asyncio
import httpx

async def main():
    async with httpx.AsyncClient() as client:
        r = await client.get("http://127.0.0.1:8001/api/properties")
        props = r.json()
        p_id = props[0]["id"]
        
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
        r = await client.post(f"http://127.0.0.1:8001/api/properties/{p_id}/negotiate", json=payload)
        neg_id = r.json()["id"]
        print(f"Negotiation ID: {neg_id}")
        
        await asyncio.sleep(5)
        
        r = await client.get(f"http://127.0.0.1:8001/api/negotiations/{neg_id}")
        print("Status:", r.json()["status"])
        print("Events:", r.json().get("events", []))
        
        r = await client.get("http://127.0.0.1:8001/api/negotiations")
        
asyncio.run(main())
