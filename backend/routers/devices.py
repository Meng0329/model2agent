"""Devices + settings router: one-time real device configuration."""
from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import db, devices

router = APIRouter(prefix="/api", tags=["devices"])


class DeviceSetting(BaseModel):
    device: str


@router.get("/devices")
def get_devices():
    """Real GPU/CPU detection (nvidia-smi + torch.cuda)."""
    return [d.__dict__ for d in devices.detect_devices()]


@router.get("/settings/device")
def get_device_setting():
    dev = db.get_setting("device", "")
    return {"device": dev, "configured": bool(dev)}


@router.put("/settings/device")
def put_device_setting(body: DeviceSetting):
    if not body.device:
        db.set_setting("device", "")
        return {"device": "", "configured": False}
    if not devices.device_available(body.device):
        raise HTTPException(400, f"device {body.device} not available")
    db.set_setting("device", body.device)
    return {"device": body.device, "configured": True}
