### Build

#### Instructions to build OpenSSL static libraries for ARM

Setup ARM cross-compiler toolchain:
```
mkdir ~/tmp && cd ~/tmp
wget https://wiki.openssl.org/images/7/70/Setenv-android.sh
. ./Setenv-android.sh
```

First, patch the `config` script for OpenSSL to compile Thumb-2 code.
Replace all `-march=armv7-a` to `-mthumb -march=armv7-a`.

Configure and build OpenSSL:
```
wget https://www.openssl.org/source/openssl-1.1.0.tar.gz
tar zxvf openssl-1.1.0.tar.gz
cd openssl-1.1.0
./config no-asm no-shared no-ssl2 no-ssl3 no-comp no-hw no-engine no-dtls no-threads -d --prefix=`pwd`/build --openssldir=`pwd`/build
make depend
make install
```