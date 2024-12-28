from typing import List, Optional
from pydantic import BaseModel

class ChannelConfig(BaseModel):
    id: int
    allowed_roles: Optional[List[str]] = None
    allowed_users: Optional[List[str]] = None

class BotConfig(BaseModel):
    token: str
    command_prefix: str = "!"
    allowed_channels: List[ChannelConfig]
    default_provider: str = "openai"
    default_model: str = "gpt-4o-mini"