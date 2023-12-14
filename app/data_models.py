from pydantic import BaseModel

class OrderData(BaseModel):
    venue_id: str
    time_received: str
    is_retail: bool


class UpdateModelPrams(BaseModel):
    new_model_path: str
    new_model_dict: str
