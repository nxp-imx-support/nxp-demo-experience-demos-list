# Video test

<!----- Boards ----->
[![License badge](https://img.shields.io/badge/License-BSD%203%20Clause-red)](./BSD-3-Clause.txt)
[![Board badge](https://img.shields.io/badge/Board-i.MX_7ULP_EVK-blue)](https://www.nxp.com/products/processors-and-microcontrollers/arm-processors/i-mx-applications-processors/i-mx-7-processors/i-mx-7ulp-family-ultra-low-power-with-graphics:i.MX7ULP)
[![Board badge](https://img.shields.io/badge/Board-i.MX_8M_Nano_EVK-blue)](https://www.nxp.com/products/processors-and-microcontrollers/arm-processors/i-mx-applications-processors/i-mx-8-applications-processors/i-mx-8m-nano-family-arm-cortex-a53-cortex-m7:i.MX8MNANO)
[![Board badge](https://img.shields.io/badge/Board-i.MX_8M_Mini_EVK-blue)](https://www.nxp.com/products/processors-and-microcontrollers/arm-processors/i-mx-applications-processors/i-mx-8-applications-processors/i-mx-8m-mini-arm-cortex-a53-cortex-m4-audio-voice-video:i.MX8MMINI)
[![Board badge](https://img.shields.io/badge/Board-i.MX_8MQuad_EVK-blue)](https://www.nxp.com/products/processors-and-microcontrollers/arm-processors/i-mx-applications-processors/i-mx-8-applications-processors/i-mx-8m-family-armcortex-a53-cortex-m4-audio-voice-video:i.MX8M)
[![Board badge](https://img.shields.io/badge/Board-i.MX_8QuadMax_MEK-blue)](https://www.nxp.com/products/processors-and-microcontrollers/arm-processors/i-mx-applications-processors/i-mx-8-applications-processors/i-mx-8-family-arm-cortex-a53-cortex-a72-virtualization-vision-3d-graphics-4k-video:i.MX8)
[![Board badge](https://img.shields.io/badge/Board-i.MX_8QuadXPlus_MEK-blue)](https://www.nxp.com/products/processors-and-microcontrollers/arm-processors/i-mx-applications-processors/i-mx-8-applications-processors/i-mx-8x-family-arm-cortex-a35-3d-graphics-4k-video-dsp-error-correcting-code-on-ddr:i.MX8X)
[![Board badge](https://img.shields.io/badge/Board-i.MX_8M_Plus_EVK-blue)](https://www.nxp.com/products/processors-and-microcontrollers/arm-processors/i-mx-applications-processors/i-mx-8-applications-processors/i-mx-8m-plus-arm-cortex-a53-machine-learning-vision-multimedia-and-industrial-iot:IMX8MPLUS)
[![Board badge](https://img.shields.io/badge/Board-i.MX_8ULP_EVK-blue)](https://www.nxp.com/products/processors-and-microcontrollers/arm-processors/i-mx-applications-processors/i-mx-8-applications-processors/i-mx-8ulp-applications-processor-family:i.MX8ULP)
[![Board badge](https://img.shields.io/badge/Board-i.MX_93_EVK-blue)](https://www.nxp.com/products/processors-and-microcontrollers/arm-processors/i-mx-applications-processors/i-mx-9-processors/i-mx-93-applications-processor-family-arm-cortex-a55-ml-acceleration-power-efficient-mpu:i.MX93)
![Language badge](https://img.shields.io/badge/Language-Python-yellow)
[![Category badge](https://img.shields.io/badge/Category-Multimedia-green)](https://www.nxp.com/docs/en/user-guide/IMX-MACHINE-LEARNING-UG.pdf)

NXP's *GoPoint for i.MX Applications Processors* unlocks a world of possibilities. This user-friendly app launches
pre-built applications packed with the Linux BSP, giving you hands-on experience with your i.MX SoC's capabilities.
Using the i.MX 7ULP, i.MX 93 or i.MX 8 family processors you can run the included *video test* application available on GoPoint
launcher as apart of the BSP flashed on to the board. For more information about GoPoint, please refer to
[GoPoint for i.MX Applications Processors User's Guide](https://www.nxp.com/IMXLINUX).

[*Voice test*](https://github.com/nxp-imx-support/nxp-demo-experience-demos-list) was used as an example to test the gstreamer video, the resolution can be configurable.

<img src="./data/diagram.svg" width="720">

## Table of Contents

- [Video test](#video-test)
  - [Table of Contents](#table-of-contents)
  - [1. Software](#1-software)
  - [2. Hardware](#2-hardware)
  - [3. Setup](#3-setup)
  - [4. Results](#4-results)
  - [5. Support](#5-support)
  - [6. Release Notes](#6-release-notes)
  - [Licensing](#licensing)

## 1. Software

*Video test* is part of Linux BSP available at [Embedded Linux for i.MX Applications Processors](https://www.nxp.com/design/design-center/software/embedded-software/i-mx-software/embedded-linux-for-i-mx-applications-processors:IMXLINUX). All the required software and dependencies to run this
application are already included in the BSP.

## 2. Hardware

To test *video test*, either the i.MX 7ULP, i.MX 93 or i.MX 8 family processors evks are required with their respective hardware components.

Component                                         | i.MX 7ULP        |i.MX 8M Plus      | i.MX 8QuadXPlus  and i.MX 8QuadMax |i.MX 8M Quad, i.MX 8M Mini and i.MX 8M Nano |i.MX 93 and i.MX 8ULP
---                                               | :---:            |:---:             | :---:                              | :---:                                      | :---:
Power Supply                                      |:white_check_mark:|:white_check_mark:|:white_check_mark:                  |:white_check_mark:                          |:white_check_mark:
HDMI Display                                      |:white_check_mark:|:white_check_mark:|:white_check_mark:                  |:white_check_mark:                          |:white_check_mark:
USB Type-C cable  (Type-A male to Type-C male)    |                  |:white_check_mark:|                                    |                                            |:white_check_mark:
USB micro-B cable  (Type-A male to Micro-B male)  |:white_check_mark:|                  |:white_check_mark:                  |:white_check_mark:                          |
HDMI cable                                        |:white_check_mark:|:white_check_mark:|:white_check_mark:                  |:white_check_mark:                          |:white_check_mark:
IMX-MIPI-HDMI (MIPI-DSI to HDMI adapter)          |                  |                  |:white_check_mark:                  |:white_check_mark:                          |:white_check_mark:
Mini-SAS cable                                    |                  |                  |:white_check_mark:                  |:white_check_mark:                          |:white_check_mark:
MIPI-CSI camera module                            |                  |:white_check_mark:|:white_check_mark:                  |:white_check_mark:                          |:white_check_mark:
USB camera (optional, if no MIPI-CSI camera used) |:white_check_mark:|:white_check_mark:|:white_check_mark:                  |:white_check_mark:                          |:white_check_mark:
Mouse                                             |:white_check_mark:|:white_check_mark:|:white_check_mark:                  |:white_check_mark:                          |:white_check_mark:
USB HUB type C                                    |:white_check_mark:|                  |:white_check_mark:                  |                                            |
USB Type-C female to USB Type-A Male              |:white_check_mark:|                  |:white_check_mark:                  |                                            |
USB Type-A Adapter (Type-A female to Type-C Male) |                  |:white_check_mark:|                                    |:white_check_mark:                          |:white_check_mark:

## 3. Setup

Launch GoPoint on the board, click on the *video test* application shown in the launcher menu. Select the **Launch Demo** button to start it. A window shows up to let the user select the camera source and resolution to be used.  

Make sure a camera module is connected, either MIPI-CSI or USB camera. Once detected and selected in the drop-down menu, start the application by clicking **Run**.

<img src="./data/first_window.png" width="360">

## 4. Results

When *video test* starts running the following is seen on display the video output that was used with the resolution selected.

<img src="./data/running_app.jpg" width="720"> 

## 5. Support

Questions regarding the content/correctness of this example can be entered as Issues within this GitHub repository.

>**Warning**: For more general technical questions, enter your questions on the [NXP Community Forum](https://community.nxp.com/)

[![Follow us on Youtube](https://img.shields.io/badge/Youtube-Follow%20us%20on%20Youtube-red.svg)](https://www.youtube.com/NXP_Semiconductors)
[![Follow us on LinkedIn](https://img.shields.io/badge/LinkedIn-Follow%20us%20on%20LinkedIn-blue.svg)](https://www.linkedin.com/company/nxp-semiconductors)
[![Follow us on Facebook](https://img.shields.io/badge/Facebook-Follow%20us%20on%20Facebook-blue.svg)](https://www.facebook.com/nxpsemi/)
[![Follow us on Twitter](https://img.shields.io/badge/Twitter-Follow%20us%20on%20Twitter-white.svg)](https://twitter.com/NXP)

## 6. Release Notes

Version | Description                         | Date
---     | ---                                 | ---
1.0.0   | Initial release                     | June 28<sup>th</sup> 2024

## Licensing

*Video test* is licensed under the [BSD-3-Clause](https://opensource.org/license/bsd-3-clause)