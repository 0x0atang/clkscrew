APP := dofever
LOCAL_PATH := $(call my-dir)

include $(CLEAR_VARS)

LOCAL_MODULE    := $(APP)
LOCAL_SRC_FILES := $(APP).c
LOCAL_LDLIBS    := -llog
LOCAL_CFLAGS    := -DSTDC_HEADERS

include $(BUILD_EXECUTABLE)