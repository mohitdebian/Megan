"""
Network Utilities

Helpers for resolving local IPs, ports, and networking features.
"""

import socket

def get_local_ip() -> str:
    """
    Get the primary local IP address of this machine on the LAN.
    This works by creating a dummy UDP connection that doesn't actually
    send any packets but forces the OS to figure out the routing interface.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP
