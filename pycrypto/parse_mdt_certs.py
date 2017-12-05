import sys
import struct
import re
import hashlib
from binascii import hexlify 

# Requirement: pip install -I M2Crypto
import M2Crypto as m2c


# ASN.1 binary signature for a SEQUENCE object
ASN1_CERT_SIG = '\x30\x82'

# Key size (in bytes)
KEY_SIZE = 256

# HAB proprietary certificate structure signature start
HAB_CERT_SIG = '\x01\x0A\x01\x00\x04'


def read_bin(fn):
    with open(fn, 'rb') as fh:
        d = fh.read()
    return d


def extract_certs_hab(data):
    offsets = [m.start() for m in re.finditer(HAB_CERT_SIG, data)]
    if len(offsets) == 0:
        return
    print "[+] Found %d HAB cert structs" % len(offsets)
    
    lst_sign = []
    lst_keys = []
    for o in offsets:
        off = o+len(HAB_CERT_SIG)
        print "[-] Parsing struct at offset %d" % o
        cert_name_len = struct.unpack("<B", data[off:off+1])[0]
        off += 1        # cert_name_len
        cert_name = data[off:off+cert_name_len]
        print "[-]   - cert_name: \t%s" % cert_name
        off += cert_name_len
        off += 11       # unknown + string_id
        issuer_name_len = struct.unpack("<B", data[off:off+1])[0]
        off += 1        # issuer_name_len
        issuer_name = data[off:off+issuer_name_len]
        print "[-]   - issuer_name: \t%s" % issuer_name
        off += issuer_name_len
        off += 2        # byte_field_id
        exp_len = struct.unpack(">H", data[off:off+2])[0]
        print "[-]   - exp_len: \t%d" % exp_len
        off += 2        # exp_len (big-endian)
        exponent = data[off:off+exp_len]
        exponent_long = int(exponent.encode('hex'), 16) 
        print "[-]   - exponent: \t%s" % hexlify(exponent)
        off += exp_len  # exponent
        mod_len = struct.unpack(">H", data[off:off+2])[0]
        print "[-]   - mod_len: \t%d" % mod_len
        off += 2        # mod_len (big-endian)
        modulus = data[off:off+mod_len]
        modulus_long = int(modulus.encode('hex'), 16) 
        print "[-]   - modulus: \t%s" % hexlify(modulus)
        off += mod_len  # modulus
        cert_sig_len = struct.unpack(">H", data[off:off+2])[0]
        print "[-]   - cert_sig_len: \t%d" % cert_sig_len
        off += 2        # cert_sig_len (big-endian)
        cert_sig = data[off:off+cert_sig_len]
        print "[-]   - cert_sig: \t%s" % hexlify(cert_sig)
        off += cert_sig_len
        
        lst_sign.append(cert_sig)
        
        pub_key = m2c.RSA.new_pub_key((
                m2c.m2.bn_to_mpi(m2c.m2.hex_to_bn(hex(exponent_long)[2:])),
                m2c.m2.bn_to_mpi(m2c.m2.hex_to_bn(hex(modulus_long)[2:])),
            ))
        lst_keys.append(pub_key)
    
    print "[+]"
    print "[+] Decrypting signatures of certs:"
    print "[-]   - cert[1].sig: \t%s" % (hexlify(lst_sign[1]))
    pt = lst_keys[0].public_decrypt(lst_sign[1], m2c.RSA.pkcs1_padding)
    print "[-]     - hash: \t%s" % (hexlify(pt[19:]))
    print "[-]     - offset: \t%d - %d" % (5262, 5649)
    
    sign = data[0x110A:0x110A+KEY_SIZE]
    print "[-]   - .sig: \t%s" % (hexlify(sign))
    pt = lst_keys[0].public_decrypt(sign, m2c.RSA.pkcs1_padding)
    print "[-]     - hash: \t%s" % (hexlify(pt[19:]))
    print "[-]     - offset: \t%d - %d" % (4276, 4362)
    
    print "\n"
    print "[+] Signature of .mdt file: offset %d - %d" % (off, off + KEY_SIZE)
    pt = lst_keys[1].public_decrypt(data[off:off+KEY_SIZE], m2c.RSA.pkcs1_padding)
    sha256hash = pt[19:]
        
    print "[-]   - RSA-PKCS1-v1.5 Signature"
    print "[-]   - Decrypted message digest: (len=%d)" % len(pt)
    print "[-]   -   hashAlgo: SHA-256"
    print "[-]   -   raw: \t%s" % hexlify(pt)
    print "[-]   -   hsh: \t%s" % hexlify(pt[19:])
    
    return sha256hash


def find_hash_input(data, sha256hash):
    """
    File offsets: 180 - 4276
    """
    print "[+] Searching for region of file being used for hash"
    sha256hash = hexlify(sha256hash)
    for start in xrange(len(data) - len(sha256hash)):
        for end in xrange(start, len(data)):
            hash_candidate = hashlib.sha256(data[start:end])
            hex_dig = hash_candidate.hexdigest()
            if hex_dig == sha256hash:
                print "[-]   - offsets: %d - %d" % (start, end)
                return


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print "usage: python %s mdt_file" % sys.argv[0]
        exit()
    
    data = read_bin(sys.argv[1])
    mdt_hash = extract_certs_hab(data)
    find_hash_input(data, mdt_hash)