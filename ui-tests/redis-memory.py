import redis
import json
import os

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6381/0")

class RedisMemory:

    def __init__(self):
        self.client = redis.from_url(
            REDIS_URL,
            decode_responses=True
        )

    def store_identity(self, name, content):
        key = f"identity:{name}"
        self.client.set(key, content)

    def get_identity(self, name):
        return self.client.get(f"identity:{name}")

    def store_tool_schema(self, session_id, schema):
        key = f"tools:{session_id}"
        self.client.set(key, json.dumps(schema))

    def get_tool_schema(self, session_id):
        data = self.client.get(f"tools:{session_id}")
        return json.loads(data) if data else None

    def store_checkpoint(self, session_id, state):
        key = f"checkpoint:{session_id}"
        self.client.set(key, json.dumps(state))

    def load_checkpoint(self, session_id):
        data = self.client.get(f"checkpoint:{session_id}")
        return json.loads(data) if data else None

    def append_episode(self, session_id, event):
        key = f"episode:{session_id}"
        self.client.rpush(key, json.dumps(event))

    def get_episodes(self, session_id, limit=20):
        key = f"episode:{session_id}"
        data = self.client.lrange(key, -limit, -1)
        return [json.loads(x) for x in data]
