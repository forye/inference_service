from pydantic import BaseModel

class OrderData(BaseModel):
    venue_id: str
    time_received: str
    is_retail: bool
