# -- coding: utf-8 --

import sys
import threading
import msvcrt
import os
import cv2
import numpy as np
import time
from ctypes import *

sys.path.append("../MvImport")
from MvCameraControl_class import *

g_bExit = False

def work_thread(cam):
    stOutFrame = MV_FRAME_OUT()
    memset(byref(stOutFrame), 0, sizeof(stOutFrame))
    
    cv2.namedWindow('Camera Feed', cv2.WINDOW_NORMAL)
    cv2.resizeWindow('Camera Feed', 800, 600)
    
    # FPS calculation variables
    frame_count = 0
    start_time = time.time()
    fps = 0

    while not g_bExit:
        ret = cam.MV_CC_GetImageBuffer(stOutFrame, 1000)
        if stOutFrame.pBufAddr is not None and ret == 0:
            frame_count += 1
            current_time = time.time()
            if current_time - start_time >= 1.0:
                fps = frame_count
                frame_count = 0
                start_time = current_time

            width = stOutFrame.stFrameInfo.nWidth
            height = stOutFrame.stFrameInfo.nHeight
            frame_len = stOutFrame.stFrameInfo.nFrameLen
            image_buffer = np.empty(frame_len, dtype=np.uint8)
            memmove(image_buffer.ctypes.data, stOutFrame.pBufAddr, frame_len)
            
            # Reshape image data to 3-channel format.
            image = image_buffer.reshape((height, width, 3))
            
            # Convert RGB to BGR
            image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
            
            # Overlay the larger FPS sign
            text = f"FPS: {fps}"
            # Increase background rectangle size to match the larger text
            cv2.rectangle(image, (10, 10), (250, 70), (0, 0, 0), -1)
            cv2.putText(image, text, (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 128), 3)
            
            cv2.imshow('Camera Feed', image)
            cv2.waitKey(1)
            
            cam.MV_CC_FreeImageBuffer(stOutFrame)
        else:
            print("no data[0x%x]" % ret)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

if __name__ == "__main__":
    # Initialize SDK
    MvCamera.MV_CC_Initialize()

    deviceList = MV_CC_DEVICE_INFO_LIST()
    tlayerType = (MV_GIGE_DEVICE | MV_USB_DEVICE | MV_GENTL_CAMERALINK_DEVICE |
                  MV_GENTL_CXP_DEVICE | MV_GENTL_XOF_DEVICE)
    ret = MvCamera.MV_CC_EnumDevices(tlayerType, deviceList)
    if ret != 0:
        print("enum devices fail! ret[0x%x]" % ret)
        sys.exit()

    if deviceList.nDeviceNum == 0:
        print("find no device!")
        sys.exit()

    print("Find %d devices!" % deviceList.nDeviceNum)
    for i in range(0, deviceList.nDeviceNum):
        mvcc_dev_info = cast(deviceList.pDeviceInfo[i], POINTER(MV_CC_DEVICE_INFO)).contents
        # Listing only basic device info here; adjust as needed.
        print("Device [%d] type: %d" % (i, mvcc_dev_info.nTLayerType))

    nConnectionNum = input("please input the number of the device to connect: ")
    if int(nConnectionNum) >= deviceList.nDeviceNum:
        print("input error!")
        sys.exit()

    cam = MvCamera()
    stDeviceList = cast(deviceList.pDeviceInfo[int(nConnectionNum)], POINTER(MV_CC_DEVICE_INFO)).contents

    ret = cam.MV_CC_CreateHandle(stDeviceList)
    if ret != 0:
        print("create handle fail! ret[0x%x]" % ret)
        sys.exit()

    ret = cam.MV_CC_OpenDevice(MV_ACCESS_Exclusive, 0)
    if ret != 0:
        print("open device fail! ret[0x%x]" % ret)
        sys.exit()
    
    if stDeviceList.nTLayerType in (MV_GIGE_DEVICE, MV_GENTL_GIGE_DEVICE):
        nPacketSize = cam.MV_CC_GetOptimalPacketSize()
        if int(nPacketSize) > 0:
            ret = cam.MV_CC_SetIntValue("GevSCPSPacketSize", nPacketSize)
            if ret != 0:
                print("Warning: Set Packet Size fail! ret[0x%x]" % ret)
        else:
            print("Warning: Get Packet Size fail! ret[0x%x]" % nPacketSize)

    # Enable frame rate control and set to 30 fps
    ret = cam.MV_CC_SetBoolValue("AcquisitionFrameRateEnable", True)
    if ret != 0:
        print("Failed to enable frame rate control! ret[0x%x]" % ret)
    else:
        ret = cam.MV_CC_SetFloatValue("AcquisitionFrameRate", 30.0)
        if ret != 0:
            print("Failed to set acquisition frame rate! ret[0x%x]" % ret)

    ret = cam.MV_CC_SetEnumValue("TriggerMode", MV_TRIGGER_MODE_OFF)
    if ret != 0:
        print("set trigger mode fail! ret[0x%x]" % ret)
        sys.exit()

    ret = cam.MV_CC_StartGrabbing()
    if ret != 0:
        print("start grabbing fail! ret[0x%x]" % ret)
        sys.exit()

    try:
        hThreadHandle = threading.Thread(target=work_thread, args=(cam,))
        hThreadHandle.start()
    except Exception as e:
        print("error: unable to start thread", e)
    
    print("Press any key to stop grabbing (or 'q' in the OpenCV window).")
    msvcrt.getch()

    g_bExit = True
    hThreadHandle.join()

    ret = cam.MV_CC_StopGrabbing()
    if ret != 0:
        print("stop grabbing fail! ret[0x%x]" % ret)
        sys.exit()

    ret = cam.MV_CC_CloseDevice()
    if ret != 0:
        print("close device fail! ret[0x%x]" % ret)
        sys.exit()

    ret = cam.MV_CC_DestroyHandle()
    if ret != 0:
        print("destroy handle fail! ret[0x%x]" % ret)
        sys.exit()

    MvCamera.MV_CC_Finalize()
    cv2.destroyAllWindows()
