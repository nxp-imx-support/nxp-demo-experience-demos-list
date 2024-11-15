# ISP Control Example Application

<!----- Boards ----->
[![License badge](https://img.shields.io/badge/License-BSD--3--Clause-red)](./BSD-3-Clause.txt)
[![Board badge](https://img.shields.io/badge/Board-i.MX_8M_Plus_EVK-blue)](https://www.nxp.com/products/processors-and-microcontrollers/arm-processors/i-mx-applications-processors/i-mx-8-applications-processors/i-mx-8m-plus-arm-cortex-a53-machine-learning-vision-multimedia-and-industrial-iot:IMX8MPLUS)
![Language badge](https://img.shields.io/badge/Language-Python-yellow)
[![Category badge](https://img.shields.io/badge/Category-Multimedia-green)](https://www.nxp.com/docs/en/user-guide/IMX_LINUX_USERS_GUIDE.pdf)

NXP's *GoPoint for i.MX Applications Processors* unlocks a world of possibilities.
This user-friendly app launches pre-built applications packed with the Linux BSP,
 giving you hands-on experience with your i.MX SoC's capabilities. Using the
 i.MX 8M Plus EVK you can run the included *ISP Control Example Application*
 available on GoPoint launcher as apart of the BSP flashed on to the board.
 For more information about GoPoint, please refer to
[GoPoint for i.MX Applications Processors User's Guide](https://www.nxp.com/IMXLINUX).

*ISP Control Example Application* showcases the *multimedia* capabilities of
 i.MX SoCs by launching a GStreamer pipeline that displays the current video
 feed and a window that allows users to change and manipulate it using API calls
 to the ISP (Image Signal Processor).

## Implementation Using GStreamer and V4L2-CTL

The Image Signal Processor (ISP) is a complete video and still picture input
 block. It contains image processing and color space conversion (RAW Bayer to YUV)
 functions. The integrated image processing unit supports simple CMOS sensors
 delivering RGB Bayer pattern without any integrated image processing and also
 image sensors with integrated YCbCr processing.

This example application uses the capabilites of this processor. First,
 a GStreamer pipeline is launched to display the output video from the
 connected camera. Once the pipeline is running, you can change some properties
 of the video feed by sending commands from the V4L2-CTL user application using
 a control panel. The VVCAM (i.MX 8M Plus ISP kernel driver integration) handles
 these commands and delivers image buffers to the GStreamer pipeline.

<img src="./data/simplified_diagram.svg" width="800">

>**NOTE:** The above block diagram is simplified and does not represent the complete GStreamer pipeline or the complete ISP software architecture. Some elements were omitted and only key elements are shown.

The following options can currently be changed through the UI:
* Black level subtraction (red, green.r, green.b, blue).
* Dewarp.
    * Dewarp on/off
    * Change dewarp mode
    * Vertical and horizontal flip
* FPS limiting
* White balance
    * Auto white balance on/off
    * White balance control (red, green.r, green.b, blue)
* Color processing
    * Color processing on/off
    * Color processing control (brightness, contrast, saturation, and hue)
* Demosaicing
    * Demosaicing on/off
    * Color processing control (brightness, contrast, saturation, and hue)
    * Threshold control
* Threshold control
    * Gamma on/off
    * Gamma mode (logarithmic or equidistant)
* Filtering
    * Filter on/off
    * Filter control (denoise and sharpness)

## Table of Contents
1. [Software](#1-software)
2. [Hardware](#2-hardware)
3. [Setup](#3-setup)
4. [Results](#4-results)
5. [FAQs](#5-faqs)
6. [Support](#6-support)
7. [Release Notes](#7-release-notes)

## 1 Software

*ISP Control Example Application* is part of Linux BSP available at [Embedded Linux for i.MX Applications Processors](https://www.nxp.com/design/design-center/software/embedded-software/i-mx-software/embedded-linux-for-i-mx-applications-processors:IMXLINUX). All the required software and dependencies to run this application are already
 included in the BSP.

i.MX Board          | Main Software Components
---                 | ---
**i.MX 8M Plus EVK** | GStreamer

>**NOTE:** If you are building the BSP using Yocto Project instead of downloading the pre-built BSP, make sure
the BSP is built for *imx-image-full*, otherwise GoPoint is not included.

## 2 Hardware

To test *ISP Control Example Application*, the i.MX 8M Plus EVK is required with
 its respective hardware components.

Component                                         | i.MX 8M Plus
---                                               | :---:
Power Supply                                      | :white_check_mark:
HDMI Display                                      | :white_check_mark:
HDMI cable                                        | :white_check_mark:
USB micro-B cable (Type-A male to Micro-B male)   | :white_check_mark:
Basler/OS08A20 camera                             | :white_check_mark:
Mouse                                             | :white_check_mark:

## 3 Setup

Connect the Basler/OS08A20 camera to the first Mini-SAS MIPI-CSI Port.
 Connect the USB micro-B cable to the USB MicroB Debug Port and to your PC, and
 connect the mouse to the Type-A Port 2. Connect the power supply to the
 Type-C Port 0 and connect the HDMI cable to the HDMI Type-A Port and
 to your HDMI display. The following diagram shows how to make the necessary
 connections:

<img src="./data/evk_connections.svg">

>**WARNING:** Please note that the MIPI-CSI Ports are not hot plug safe. If you plug or unplug the cameras while the board is powered on, you may damage the board.

For this application you need to change the device tree.
 To do that do the following:
 - Open the Arm Cortex-A core console as descibed in the Section 3:
  **Basic Terminal Setup** of the [i.MX Linux User's Guide](https://www.nxp.com/docs/en/user-guide/IMX_LINUX_USERS_GUIDE.pdf)
  , then press any key to enter U-Boot console.

 - There, enter the following command: `fatls mmc ${mmcdev}:${mmcpart}`.
  You should see a list of all available device tree files. Make sure
  the device trees **imx8mp-evk-basler.dtb** and **imx8mp-evk-os08a20.dtb**
  are listed.

 - Change the device tree using the `editenv fdtfile` command. Replace the
 .dtb file with **imx8mp-evk-basler.dtb** or **imx8mp-evk-os08a20.dtb**
 , depending on which camera you are using, and enter the `boot` command.

 - *Optional*. You can save this configuration using the `saveenv` command to
 the next time you use the board.

Launch GoPoint on the board and click on the *ISP Control Example Application*
 application shown in the launcher menu. Select the **Launch Demo** button to
 start it. A full-screen window shows up with the video source from the
 Basler/OS08A20 camera and a control panel after the video is started.

## 4 Results

When *ISP Control Example Application* starts running, the following is seen
 on the screen:

1. A full screen window showing the video source from the Basler/OS08A20 camera.
2. A window with a control panel to manipulate the video feed.

<img src="./data/ISP_Control_Demo.webp" width="720">

## 5 FAQs

### The example application does not run and just opens a window with the message "No compatible camera found! (Basler or OS08A20)"

This could be happening for 3 main reasons:
 1. You selected the wrong device tree file.
 2. There is a problem with your camera connection.
 3. The camera that you connected to the board is not the correct one
  (Basler or OS08A20).

 Make sure that the above scenarios are not the case.

## 6 Support

>**Warning**: For more general technical questions, enter your questions on the [NXP Community Forum](https://community.nxp.com/)

[![Follow us on Youtube](https://img.shields.io/badge/Youtube-Follow%20us%20on%20Youtube-red.svg)](https://www.youtube.com/NXP_Semiconductors)
[![Follow us on LinkedIn](https://img.shields.io/badge/LinkedIn-Follow%20us%20on%20LinkedIn-blue.svg)](https://www.linkedin.com/company/nxp-semiconductors)
[![Follow us on Facebook](https://img.shields.io/badge/Facebook-Follow%20us%20on%20Facebook-blue.svg)](https://www.facebook.com/nxpsemi/)
[![Follow us on Twitter](https://img.shields.io/badge/Twitter-Follow%20us%20on%20Twitter-white.svg)](https://twitter.com/NXP)

## 7. Release Notes

Version | Description                         | Date
---     | ---                                 | ---
1.0.0   | Initial release                     | June 28<sup>th</sup> 2024


## Licensing

*ISP Control Example Application* is licensed under the
 [BSD-3-Clause](https://opensource.org/license/bsd-3-clause).

## Origin

GStreamer documentation: https://gstreamer.freedesktop.org/documentation/index.html?gi-language=python \
Software ISP Application Note: https://www.nxp.com/docs/en/application-note/AN12060.pdf
