# i.MX93 Low Power Machine Learning

i.MX93's Low Power Machine Learning application showcases the i.MX93's machine learning capabilities in low power use
case by using Cortex-M33 core to run ML model inference with tflite-micro framework. When running the application, the
Cortex-A55 core, which runs Linux, will be put into suspend mode to save power consumption. NPU is not used in this
application for the same reason. 

Two applications are implemented in current release:

1. **Baby cry detection:** This application records one second of audio input from MIC array on the i.MX93 EVK board, 
   and tries to identify whether there is baby crying sound in the audio by running ML model inference. If baby crying
   sound is detected, it will wake up Cortex-A55 core and stop. If baby crying sound is not detected, it will suspend
   Cortex-M33 core for a configurable time interval and wake up Cortex-M33 core to record one second audio again, and
   run the same process in an infinite loop until a baby crying sound is detected.

2. **Key-word Spot:** This application records one second audio input from MIC array on the i.MX93 EVK board, and tries
   to identify whether there is key-word "UP" in the audio by running ML model inference. If key-word is detected, it
   will wake up Cortex-A55 core and stop. If no key-word is detected, it will record one second audio again, and run
   the same process in an infinite loop until a key-word is detected.

## ML models

The ML model used in baby cry detection is trained by NXP and licensed under
[BSD-3-Clause](https://opensource.org/license/bsd-3-clause/) license. The ML model used in key-word spot application is
originally from [ARM-software](https://github.com/ARM-software/ML-KWS-for-MCU/blob/master/Pretrained_models/DS_CNN/DS_CNN_S.pb)
under [Apache-2.0](https://www.apache.org/licenses/LICENSE-2.0) license.

## Source code and build steps

The Cortex-M33 image of these two applications need to be compiled with i.MX93's Cortex-M33 SDK. The source code is
released in patch format in [GitHub - nxp-imx-support/nxp-demo-experience-assets](https://github.com/nxp-imx-support/nxp-demo-experience-assets).
To build these two binaries, please follow below steps:

1. Generate and download i.MX93's Cortex-M33 SDK from [MCUXpresso](https://mcuxpresso.nxp.com/). Please select i.MX93
EVK as board, 2.14.0 as SDK version, Linux as Host OS and ARM GCC as Toolchain.

2. Unpack i.MX93's Cortex-M33 SDK package on Linux Host PC and setup toolchain according to the user's guide in SDK
package. Then create a `git init` repo in the unpacked SDK folder for patch applying.

3. Download the patch "*0001-Add-low-power-baby-cry-detection-demo.patch*" and "*0001-Add-low-power-kws-detection-demo.patch*"
from [GitHub - nxp-imx-support/nxp-demo-experience-assets](https://github.com/nxp-imx-support/nxp-demo-experience-assets)
under patches folder. Then apply these two patches in the i.MX93's Cortex-M33 SDK folder.

4. Move to folder `M33_SDK/boards/mcimx93evk/demo_apps/lp_baby_detection/armgcc/` and run `build_release.sh` script to
build Cortex-M33 image for baby cry detection application. Move to folder `M33_SDK/boards/mcimx93evk/demo_apps/lp_kws_detection/armgcc/`
and run `build_release.sh` script to build Cortex-M33 image for key-word spot application.
