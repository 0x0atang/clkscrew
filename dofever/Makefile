app := dofever
arch := v7a
all: clean compile clean-partial

compile:
	mkdir jni
	cp *.c jni
	cp *.h jni
	cp Android.mk jni
	cp Application.mk jni
	ndk-build
	mv libs/armeabi-v7a/$(app) ./$(app)-v7a
	mv libs/arm64-v8a/$(app) ./$(app)-v8a
	rm -rf libs obj jni

install:
	adb push $(app)-$(arch) /data/local/tmp

clean: clean-app clean-partial

clean-app:
	rm -f $(app)-v7a $(app)-v8a
	
clean-partial:
	rm -rf libs obj jni
