## i.MX Demo Launcher - Demo List

#### Project bitbucket page:

https://bitbucket.sw.nxp.com/projects/IMXS/repos/imx-demo-launcher-demos-list/browse

#### Download: 

git clone https://bitbucket.sw.nxp.com/scm/imxs/imx-demo-launcher-demos-list.git

### How to add a new demo

Add the new demo on file demos.json.

* name: Name of the demo. 
* executable: Executable command to launch de demo.
* source: Link to the source code. (**optional**) 
* icon: Icon file to represent the demo. (**optional**)
* screenshot: Screenshot file of the demo. (**optional**)
* compatible: List of compatible boards.
* description: Description of the demo.

**Important**: All the demos must be inside 2 categories, in the example below, "Camera Preview" is inside Multimedia and Video4Linux2 categories.

Upload the screenshots and icons inside the "screenshot" and "icon" folders.

Example:

    "multimedia":[{
        "Video4Linux2":[{
            "name": "Camera Preview",
            "executable": "/unittests/v4l2/mxc_v4l2_capture",
            "source": "https://source.codeaurora.org/external/imx/imx-test/tree/test/mxc_v4l2_test/mxc_v4l2_capture.c?h=imx_4.14.98_2.0.0_ga",
            "icon": "v4l2_cam_prev_icon.png",
            "screenshot": "v4l2_cam_prev_screenshot.png",
            "compatible": "imx7ulpevk, imx8qmmek",
            "description": "Description of v4l2 camera preview" }]

After adding the new demo, you can check if the new entry is in a valid JSON format by copying the entire file text and pasting on the site: **http://json.parser.online.fr/**

### Available "compatible" list

* imx7ulpevk
* imx8qxpmek
