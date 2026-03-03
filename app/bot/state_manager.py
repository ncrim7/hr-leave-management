import redis.asyncio as redis
import json
from typing import Optional, Any
from app.core.config import settings

redis_client = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    decode_responses=True
)

class StateManager:
    @staticmethod
    async def set_state(user_id: int, state: str, **kwargs):
        """Set user state and optional extra data, expiring in 1 hour."""
        data = {"state": state}
        if kwargs:
            data.update(kwargs)
        await redis_client.setex(f"user:{user_id}:state", 3600, json.dumps(data))

    @staticmethod
    async def get_state_data(user_id: int) -> dict:
        """Get the current state and data for a user."""
        data = await redis_client.get(f"user:{user_id}:state")
        if data:
            return json.loads(data)
        return {"state": "IDLE"}

    @staticmethod
    async def clear_state(user_id: int):
        """Clear user state."""
        await redis_client.delete(f"user:{user_id}:state")

    @staticmethod
    async def update_state_data(user_id: int, **kwargs):
        """Update specific data in the current state without changing the state string."""
        current_data = await StateManager.get_state_data(user_id)
        current_data.update(kwargs)
        await redis_client.setex(f"user:{user_id}:state", 3600, json.dumps(current_data))
