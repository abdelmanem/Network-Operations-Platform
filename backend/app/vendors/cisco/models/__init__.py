"""Cisco platform model definitions."""

from backend.app.vendors.cisco.models.aironet import AIRONET_1131
from backend.app.vendors.cisco.models.ce500 import CATALYST_EXPRESS_500
from backend.app.vendors.cisco.models.ios import CATALYST_2960, CATALYST_3560
from backend.app.vendors.cisco.models.iosxe import CATALYST_2960X

__all__ = [
    "AIRONET_1131",
    "CATALYST_2960",
    "CATALYST_2960X",
    "CATALYST_3560",
    "CATALYST_EXPRESS_500",
]
