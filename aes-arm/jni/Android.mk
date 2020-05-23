APP := aes_cbc
LOCAL_PATH := $(call my-dir)

### Include openssl libraries as a prebuilt libs ###

include $(CLEAR_VARS)

LOCAL_MODULE            := openssl-crypto
LOCAL_SRC_FILES         := $(LOCAL_PATH)/openssl/lib/libcrypto.a
LOCAL_EXPORT_C_INCLUDES := $(LOCAL_PATH)/openssl/include

include $(PREBUILT_STATIC_LIBRARY)


### Build your ndk lib ###

# Build options:
#   -mthumb: force thumb mode (similar to trustzone code)
#   -O0:     disable optimization (aid debugging)
#   -g:      include debugging symbols (aid debugging)

include $(CLEAR_VARS)

LOCAL_MODULE            := $(APP)
LOCAL_C_INCLUDES        := $(LOCAL_PATH) \
                           $(LOCAL_PATH)/openssl/include
LOCAL_SRC_FILES         := $(APP).c
LOCAL_LDLIBS            := -llog -fPIE -pie
LOCAL_CFLAGS            := -DSTDC_HEADERS -mtune=cortex-a8 -fPIE -mthumb -O0 -g
LOCAL_STATIC_LIBRARIES  := openssl-crypto

include $(BUILD_EXECUTABLE)
