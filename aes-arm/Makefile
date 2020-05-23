app := aes_cbc

all: compile clean-partial

compile:
	cd jni && ndk-build NDK_DEBUG=1
	mv libs/armeabi/$(app) .
	mv obj/local/armeabi/$(app) ./$(app)_DEBUG

install:
	adb push $(app) /data/local/tmp

run: install
	adb shell /data/local/tmp/$(app)

clean: clean-app clean-partial

clean-app:
	rm -f $(app) $(app)_DEBUG

clean-partial:
	rm -rf libs obj