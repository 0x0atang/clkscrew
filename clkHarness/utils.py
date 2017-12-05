import os
import time
import socket
import numpy as np

def ensure_dir(path):
    """ Create folder if it doesn't exist.
    """
    try: 
        os.makedirs(path)
    except OSError:
        if not os.path.isdir(path):
            raise

def iqr_mean(n, percentile_lo=25, percentile_hi=75):
    """ Compute mean of elements in the list within the interquartile range.
    """
    n = np.array(n)
    hi, lo = np.percentile(n,[percentile_hi, percentile_lo])
    nn = n[(n >= lo) & (n <= hi)]
    return np.mean(nn)


def verbalize_reset(ip='10.211.55.2', port=10001):
    # Create a TCP/IP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    # Connect the socket to the port where the server is listening
    server_address = (ip, port)
    sock.connect(server_address)
    
    time.sleep(1)
    sock.close()