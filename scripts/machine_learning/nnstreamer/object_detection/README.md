# Object Detection - NXP NNStreamer Example


<!----- Boards ----->

[![License
badge](https://img.shields.io/badge/License-BSD%203%20Clause-red.png)](./BSD-3-Clause.txt)
[![Language
badge](https://img.shields.io/badge/Language-C++-yellow.png)](./)
[![Board
badge](https://img.shields.io/badge/Board-EVK–MIMX8MP-blue.png)](https://www.nxp.com/pip/8MPLUSLPD4-EVK)
[![Board
badge](https://img.shields.io/badge/Board-MCIMX93–EVK-blue.png)](https://www.nxp.com/products/processors-and-microcontrollers/arm-processors/i-mx-applications-processors/i-mx-9-processors/i-mx-93-applications-processor-family-arm-cortex-a55-ml-acceleration-power-efficient-mpu:i.MX93)
[![Board
badge](https://img.shields.io/badge/Board-IMX95LPD5EVK–19-blue.png)](https://www.nxp.com/products/processors-and-microcontrollers/arm-processors/i-mx-applications-processors/i-mx-9-processors/i-mx-95-applications-processor-family-high-performance-safety-enabled-platform-with-eiq-neutron-npu:iMX95)
[![Board
badge](https://img.shields.io/badge/Board-EVK–MIMX8MM-blue.png)](https://www.nxp.com/pip/8MMINILPD4-EVK)
[![Board
badge](https://img.shields.io/badge/Board-MEK–MIMX8QM-blue.png)](https://www.nxp.com/pip/MCIMX8QM-CPU)
[![Category
badge](https://img.shields.io/badge/Category-AI/ML-yellowgreen.png)](https://www.nxp.com/docs/en/user-guide/IMX-MACHINE-LEARNING-UG.pdf)

NXP’s *GoPoint for i.MX Applications Processors* unlocks a world of
possibilities. This user-friendly app launches pre-built applications
packed with the Linux BSP, giving you hands-on experience with your i.MX
SoC’s capabilities. Using the supported i.MX boards you can run the
included *Object Detection* example available on GoPoint launcher as
apart of the BSP flashed on to the board. For more information about
GoPoint, please refer to [GoPoint for i.MX Applications Processors
User’s Guide](https://www.nxp.com/IMXLINUX).

*Object Detection* showcases the *Machine Learning* (ML) capabilities of
i.MX SoCs by using a *Neural Processing Unit* (NPU). Object detection is
the ML task that detects instances of objects of a certain class within
an image. A bounding box and a class label are found for each detected
object.

This application is developed using GStreamer and NNStreamer, written in
C++. On the i.MX 93, *PXP* acceleration is used for the color space
conversion and frame resizing during pre-processing and post-processing
of data. On i.MX 8M and i.MX 95 boards, the *2D-GPU* accelerator is used
for the same purpose if available.

## GStreamer + NNStreamer pipeline

> **NOTE:** This block diagram is simplified and do not represent the
> complete GStreamer + NNStreamer pipeline elements. Some elements were
> omitted and only the key elements are shown. This pipeline applies for
> the examples accelerated with NPU and GPU/PXP only.

<img src="./data/simplified_diagram.svg" style="width:95.0%"
data-fig-alt="Simplified pipeline in GStreamer + NNStreamer"
data-fig-align="center" />

## Table of Contents

1.  [Software](#step1)
2.  [Hardware](#step2)
3.  [Setup](#step3)
4.  [Results](#step4)
5.  [FAQs](#step5)
6.  [Support](#step6)
7.  [Release Notes](#step7)

## 1. Software

*Object detection* is part of Linux BSP available at [Embedded Linux for
i.MX Applications
Processors](https://www.nxp.com/design/design-center/software/embedded-software/i-mx-software/embedded-linux-for-i-mx-applications-processors:IMXLINUX).
All the required software and dependencies to run this application are
already included in the BSP.

| i.MX Board       | Main Software Components                          |
|------------------|---------------------------------------------------|
| **i.MX 8M Plus** | GStreamer + NNStreamer<br>VX Delegate (NPU & GPU) |
| **i.MX 93**      | GStreamer + NNStreamer<br>Ethos-U Delegate (NPU)  |
| **i.MX 95**      | GStreamer + NNStreamer<br>Neutron Delegate (NPU)  |

### Model information

#### SSD-Lite-MobileNet-V2-COCO (no postprocess)

This example uses the SSD-Lite-MobileNet-V2-COCO model without
post-processing included. Post-processing is done in Cortex-A. The model
is trained with [COCO](https://cocodataset.org/) dataset.

| Information  | Value                                |
|--------------|--------------------------------------|
| Input shape  | RGB image \[1, 300, 300, 3\]         |
| Output shape | \[1, 1917, 1, 4\]<br>\[1, 1917, 91\] |

### Benchmarks

The quantized INT8 models have been tested on i.MX using
`./benchmark_model` tool (see [i.MX Machine Learning User’s
Guide](https://www.nxp.com/docs/en/user-guide/IMX-MACHINE-LEARNING-UG.pdf)).

#### Performance avg. inference time

| Platform     | CPU (ms) | NPU (ms) | GPU (ms) |
|--------------|:--------:|:--------:|:--------:|
| i.MX 95      |          |          |   TBD    |
| i.MX 93      |          |          |   N/A    |
| i.MX 8M Plus |  47.55   |  16.30   |  477.48  |
| i.MX 8M Mini |          |   N/A    |   N/A    |
| i.MX 8QM     |          |   N/A    |          |

> **NOTE 1:** CPU inference time is benchmarked for max number of
> threads in each board. For example, i.MX 8M Plus uses 4 threads to
> achieve 47.55 ms avg. inference speed with Cortex-A. Benchmarked using
> *BSP LF6.6.36_2.1.0*.

> **NOTE 2:** GPU inference benchmark computed with full-precision FP32
> model.

### Example GStreamer + NNStreamer command-line pipeline

Below is the GStreamer + NNStreamer pipeline populated by the C++
example in i.MX 8M Plus. This pipeline can be executed in directly in
console, but performance numbers won’t show in display. To use all
features, please run the example from GoPoint launcher.

``` bash
gst-launch-1.0 v4l2src name=cam_src device=/dev/video3 num-buffers=-1 ! \
  video/x-raw,width=640,height=480,framerate=30/1 ! tee name=t 
    t. ! queue name=thread-nn max-size-buffers=2 leaky=2 ! \
      imxvideoconvert_g2d ! video/x-raw,width=300,height=300,format=RGBA ! \
      videoconvert ! video/x-raw,format=RGB ! tensor_converter ! \
      tensor_filter latency=1 framework=tensorflow-lite \
      model=/opt/gopoint-apps/downloads/ssdlite_mobilenet_v2_coco_quant_uint8_float32_no_postprocess.tflite \
      custom=Delegate:External,ExtDelegateLib:libvx_delegate.so name=detection_filter ! \
      tensor_decoder mode=bounding_boxes option1=mobilenet-ssd \
      option2=/opt/gopoint-apps/downloads/coco_labels_list.txt \
      option3=/opt/gopoint-apps/downloads/box_priors.txt option4=640:480 option5=300:300 ! \
      imxvideoconvert_g2d ! mix. \
    t. ! queue name=thread-img max-size-buffers=2 leaky=2 ! \
      imxcompositor_g2d name=mix sink_0::zorder=2 sink_1::zorder=1 latency=20000000 min-upstream-latency=20000000 ! \
      cairooverlay name=perf ! \
      fpsdisplaysink name=img_tensor text-overlay=false video-sink=waylandsink sync=false
```

## 2. Hardware

### Supported backends for ML inference

<table style="width:71%;">
<colgroup>
<col style="width: 23%" />
<col style="width: 23%" />
<col style="width: 23%" />
</colgroup>
<thead>
<tr class="header">
<th>CPU</th>
<th>NPU</th>
<th>GPU</th>
</tr>
</thead>
<tbody>
<tr class="odd">
<td><ul>
<li>i.MX 8M Plus</li>
<li>i.MX 8M Mini</li>
<li>i.MX 8QM</li>
<li>i.MX 93</li>
<li>i.MX 95</li>
</ul></td>
<td><ul>
<li>i.MX 8M Plus</li>
<li>i.MX 93</li>
<li>i.MX 95</li>
</ul></td>
<td><ul>
<li>i.MX 8M Plus</li>
<li>i.MX 8QM</li>
</ul></td>
</tr>
</tbody>
</table>

To test *Object Detection* you will need the following hardware:

- i.MX EVK for selected SoC
- Mouse
- Camera (MIPI-CSI or USB)
- HDMI Monitor or supported display

## 3. Setup

### Using Basler or OS08A20 cameras (Optional, only for i.MX 8M Plus)

If you want to use these cameras, you need to change the device tree:

- Open the Arm Cortex-A core console as descibed in the Section 3:
  **Basic Terminal Setup** of the [i.MX Linux User’s
  Guide](https://www.nxp.com/docs/en/user-guide/IMX_LINUX_USERS_GUIDE.pdf),
  then press any key to enter U-Boot console.

- There, enter the following command: `fatls mmc ${mmcdev}:${mmcpart}`.
  You should see a list of all available device tree files. Make sure
  the device trees **imx8mp-evk-basler.dtb** and
  **imx8mp-evk-os08a20.dtb** are listed.

- Change the device tree using the `editenv fdtfile` command. Replace
  the .dtb file with **imx8mp-evk-basler.dtb** or
  **imx8mp-evk-os08a20.dtb**, depending on which camera you are using,
  and enter the `boot` command.

- *Optional:* You can save this configuration using the `saveenv`
  command for the next time you use the board. Run this command in
  u-boot before booting the system.

### Launching Object Detection

Launch GoPoint on the board and click on the *Object Detection*
application shown in the launcher menu. Select the **Launch Demo**
button to start it. A window shows up to let the user select the camera
source, backend and text color to be used. Make sure a camera module is
connected, ether MIPI-CSI or USB camera. Once detected and selected in
the drop-down menu, start the application by clicking **Run Object
Detection**.

<img src="./data/launch_demo.jpg" style="width:40.0%" data-fig-align="center" />

When running the application on i.MX 8M Plus and i.MX 95, a warm-up time
is needed for models to be ready for acceleration on the NPU. On i.MX
93, the models are compiled using vela compiler for Ethos-U NPU
acceleration. The process is done automatically, but takes a couple of
minutes on each board. Once the process finishes and models are ready,
the application starts right away. This only happens during first time
running the application, since compiled models are stored on the cache
for future use.

> **NOTE:** Cache is currently not enabled in i.MX 95. Every time this
> application is executed, the warm up time is required.

## 4. Results

When *Object Detection* starts running the following is seen on display:

1.  If `Display performance (FPS/IPS)` flag is enabled, performance
    information is displayed at the top left corner. This will be
    printed in the color specified by the text color selected in the
    launcher.
2.  Video stream showing the detected object present in the scene. The
    detected object will be shown inside a box with its corresponding
    label at the top left corner.

<img src="./data/vase.jpg" style="width:40.0%" data-fig-align="center" />

<img src="./data/apple.jpg" style="width:40.0%" data-fig-align="center" />

3.  The object detection demo can identify more than a single object at
    a time.

<img src="./data/ObjectDetection.webp" style="width:90.0%" data-fig-align="center" />

## 5. FAQs

### Is the source code of Object Detection available?

Yes, the source code is available under the
[BSD-3-Clause](./BSD-3-Clause.txt) at
https://github.com/nxp-imx/nxp-nnstreamer-examples. There is more
information on how to cross-compile the application for stand-alone
deployment.

### The GTK+3 GUI windows close unexpectedly when running the application

This is a known issue and we are working on it. Sometimes the windows
close unexpectedly. If this happens, please relaunch the application.
Most of the times this does not affect the execution of the application.

### Models are failing to download from server

Please make sure the internet connection is up and running on the board.
The application requires an internet connection to download the models.
If internet connection is available, please update the time and date of
the board before trying to download the models again. Some servers might
block the downloads for security reasons when the time and date of board
is not updated. Some companies might also block their networks
preventing the models to be downloaded; if this is the case, try using
another connection such as a mobile device working as hotspot (Wi-Fi
connVection is required).

<img src="./data/internet_error.jpg" style="width:40.0%" data-fig-align="center" />

### Files are corrupted

It is possible that files get corrupted during download process due to
different reasons, such as a connection shutdown. If this happens, the
files won’t be loaded to the application. To fix this, the easy solution
is to clean the following path on the board:
`/opt/gopoint-apps/downloads`. Remove all files and try running the
application again. If lucky, the files will be downloaded successfully
next time.

<img src="./data/corrupted.jpg" style="width:40.0%" data-fig-align="center" />

## 6. Support

Questions regarding the content/correctness of this example can be
entered as Issues within this GitHub repository.

> **Warning**: For more general technical questions regarding NXP
> Microcontrollers and the difference in expected functionality, enter
> your questions on the [NXP Community
> Forum](https://community.nxp.com/)

[![Follow us on
Youtube](https://img.shields.io/badge/Youtube-Follow%20us%20on%20Youtube-red.svg)](https://www.youtube.com/NXP_Semiconductors)
[![Follow us on
LinkedIn](https://img.shields.io/badge/LinkedIn-Follow%20us%20on%20LinkedIn-blue.svg)](https://www.linkedin.com/company/nxp-semiconductors)
[![Follow us on
Facebook](https://img.shields.io/badge/Facebook-Follow%20us%20on%20Facebook-blue.svg)](https://www.facebook.com/nxpsemi/)
[![Follow us on
Twitter](https://img.shields.io/badge/X-Follow%20us%20on%20X-black.svg)](https://x.com/NXP)

## 7. Release Notes

| Version | Description / Update |                          Date |
|:-------:|----------------------|------------------------------:|
|   1.0   | Initial release      | December 16<sup>th</sup> 2024 |

## Licensing

*Object Detection* is licensed under the
[BSD-3-Clause](https://opensource.org/license/BSD-3-Clause) License.
