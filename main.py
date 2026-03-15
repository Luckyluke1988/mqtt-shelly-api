import json
import os
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional

import paho.mqtt.client as mqtt
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn


MQTT_HOST = os.getenv("MQTT_HOST", "192.168.10.51")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "root")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "root")
MQTT_CLIENT_ID = os.getenv("MQTT_CLIENT_ID", "shelly-gen4-mvp")

HTTP_HOST = os.getenv("HTTP_HOST", "0.0.0.0")
HTTP_PORT = int(os.getenv("HTTP_PORT", "8000"))


@dataclass
class DeviceState:
    device_id: str
    online: Optional[bool] = None
    last_seen: float = field(default_factory=time.time)
    status_topics: Dict[str, Any] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)
    last_rpc_response: Optional[dict[str, Any]] = None


DEVICES: dict[str, DeviceState] = {}
LOCK = threading.Lock()


def get_or_create_device(device_id: str) -> DeviceState:
    if device_id not in DEVICES:
        DEVICES[device_id] = DeviceState(device_id=device_id)
    return DEVICES[device_id]


def try_parse_json(payload: str) -> Any:
    try:
        return json.loads(payload)
    except Exception:
        return payload


class RpcRequest(BaseModel):
    method: str
    params: Optional[dict] = None


class SwitchCommand(BaseModel):
    on: bool
    channel: int = 0


app = FastAPI(title="Shelly Gen4 MQTT MVP", version="0.1.0")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/devices")
def list_devices():
    with LOCK:
        return {
            "count": len(DEVICES),
            "devices": [asdict(d) for d in DEVICES.values()]
        }


@app.get("/devices/{device_id}")
def get_device(device_id: str):
    with LOCK:
        device = DEVICES.get(device_id)
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")
        return asdict(device)


@app.post("/devices/{device_id}/rpc")
def send_rpc(device_id: str, req: RpcRequest):
    payload = {
        "id": str(uuid.uuid4()),
        "src": MQTT_CLIENT_ID,
        "method": req.method,
    }
    if req.params is not None:
        payload["params"] = req.params

    topic = f"{device_id}/rpc"
    MQTT_BRIDGE.publish(topic, json.dumps(payload))
    return {"published": True, "topic": topic, "payload": payload}


@app.post("/devices/{device_id}/switch")
def switch_set(device_id: str, cmd: SwitchCommand):
    payload = {
        "id": str(uuid.uuid4()),
        "src": MQTT_CLIENT_ID,
        "method": "Switch.Set",
        "params": {
            "id": cmd.channel,
            "on": cmd.on
        }
    }
    topic = f"{device_id}/rpc"
    MQTT_BRIDGE.publish(topic, json.dumps(payload))
    return {"published": True, "topic": topic, "payload": payload}


class MqttBridge:
    def __init__(self):
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=MQTT_CLIENT_ID)
        if MQTT_USERNAME:
            self.client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect

    def start(self):
        self.client.connect(MQTT_HOST, MQTT_PORT, 60)
        self.client.loop_start()

    def stop(self):
        try:
            self.client.loop_stop()
        finally:
            self.client.disconnect()

    def publish(self, topic: str, payload: str):
        info = self.client.publish(topic, payload=payload, qos=1, retain=False)
        info.wait_for_publish()

    def on_connect(self, client, userdata, flags, reason_code, properties):
        print(f"[MQTT] connected: {reason_code}")

        # Shelly Gen2+/Gen4 topics
        client.subscribe("+/online", qos=1)
        client.subscribe("+/status/#", qos=1)
        client.subscribe("+/events/rpc", qos=1)
        client.subscribe("+/response/rpc", qos=1)

    def on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties):
        print(f"[MQTT] disconnected: {reason_code}")

    def on_message(self, client, userdata, msg):
        topic = msg.topic
        raw = msg.payload.decode("utf-8", errors="ignore")
        payload = try_parse_json(raw)

        parts = topic.split("/")
        if len(parts) < 2:
            return

        device_id = parts[0]

        with LOCK:
            device = get_or_create_device(device_id)
            device.last_seen = time.time()

            if parts[1] == "online":
                device.online = str(raw).lower() == "true"
                return

            if parts[1] == "status":
                component = "/".join(parts[2:])
                device.status_topics[component] = payload
                return

            if len(parts) >= 3 and parts[1] == "events" and parts[2] == "rpc":
                if isinstance(payload, dict):
                    device.events.append(payload)
                    device.events = device.events[-20:]
                return

            if len(parts) >= 3 and parts[1] == "response" and parts[2] == "rpc":
                if isinstance(payload, dict):
                    device.last_rpc_response = payload
                return


MQTT_BRIDGE = MqttBridge()


@app.on_event("startup")
def startup():
    MQTT_BRIDGE.start()


@app.on_event("shutdown")
def shutdown():
    MQTT_BRIDGE.stop()


if __name__ == "__main__":
    uvicorn.run(app, host=HTTP_HOST, port=HTTP_PORT)