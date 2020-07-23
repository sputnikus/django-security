try:
    from ipware.ip import get_client_ip
except ImportError:
    from ipware.ip2 import get_client_ip
