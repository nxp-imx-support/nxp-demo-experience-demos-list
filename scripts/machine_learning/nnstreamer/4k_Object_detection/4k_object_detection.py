#!/usr/bin/env python3

"""
Copyright 2025 NXP

SPDX-License-Identifier: BSD-3-Clause

This script launches the Object Detection NNStreamer example using a UI to pick settings.
"""

import os
import sys
import threading
import glob
import subprocess
import time
import gi
import numpy as np
import cv2
from datetime import datetime
import shutil

# Check for correct Gtk version
gi.require_version("Gtk", "3.0")
gi.require_version('Gst', '1.0')
from gi.repository import Gtk as gtk
from gi.repository import GLib
from gi.repository import Gst

# Initialize GStreamer
Gst.init(None)

# Import utils
sys.path.append("/opt/gopoint-apps/scripts/")
import utils

MODELS_PATH = "/opt/gopoint-apps/downloads/"


def threaded(fn):
    """
    Handle threads out of main GTK thread
    """

    def wrapper(*args, **kwargs):
        threading.Thread(target=fn, args=args, kwargs=kwargs).start()

    return wrapper


class PersonDetectionHandler:
    def __init__(self, save_dir, labels_path):
        self.frame_count = 0
        self.total_persons_detected = 0
        self.saved_images_count = 0
        self.last_save_time = 0
        self.save_interval = 5.0  # 5 seconds delay between saves
        self.max_images = 5  # Maximum number of images to keep
        self.current_image_index = 1  # Start with image_1
        self.original_frame_cache = None
        self.cache_lock = threading.Lock()
        self.save_dir = save_dir
        self.display_image_path = os.path.join(save_dir, "display_image.jpg")
        self.current_display_source = "image_1.jpg"
        self.main_pipeline = None
        self.image_pipeline = None
        self.image_reload_interval = 3.0  # Reload image every 3 seconds
        self.load_coco_labels(labels_path)
        
    def load_coco_labels(self, labels_path):
        """Load COCO labels to identify person class"""
        try:
            with open(labels_path, 'r') as f:
                self.labels = [line.strip() for line in f.readlines()]
            print(f"Loaded {len(self.labels)} COCO labels")
            
            # Find person class index (usually index 0 in COCO)
            self.person_class_id = None
            for i, label in enumerate(self.labels):
                if label.lower() == 'person':
                    self.person_class_id = i
                    print(f"Person class found at index: {i}")
                    break
            
            if self.person_class_id is None:
                print("Warning: 'person' class not found in labels, using index 0")
                self.person_class_id = 0
                
        except Exception as e:
            print(f"Error loading labels: {e}")
            self.labels = ['person']  # Fallback
            self.person_class_id = 0
    
    def create_image_pipeline(self):
        """Create a separate pipeline for image display using intervideosink"""
        try:
            image_pipeline_str = f"""
            filesrc location={self.display_image_path} ! 
            jpegdec ! 
            imagefreeze ! 
            videoconvert ! 
            videoscale ! 
            video/x-raw,width=960,height=540,format=RGBA,framerate=5/1 ! 
            intervideosink channel=image_channel
            """
            
            self.image_pipeline = Gst.parse_launch(image_pipeline_str)
            print("? Created separate image pipeline with intervideosink")
            return True
                
        except Exception as e:
            print(f"? Error creating image pipeline: {e}")
            return False
    
    def restart_image_pipeline(self):
        """Restart the image pipeline to reload the image"""
        try:
            if self.image_pipeline is None:
                return True
            
            print(f"?? Restarting image pipeline...")
            
            # Stop the image pipeline
            self.image_pipeline.set_state(Gst.State.NULL)
            
            # Wait a moment
            time.sleep(0.2)
            
            # Start it again
            ret = self.image_pipeline.set_state(Gst.State.PLAYING)
            if ret == Gst.StateChangeReturn.FAILURE:
                print("? Failed to restart image pipeline")
            else:
                print(f"? Image pipeline restarted - showing: {self.current_display_source}")
            
            return True
            
        except Exception as e:
            print(f"? Error restarting image pipeline: {e}")
            return True
    
    def update_display_image(self, new_image_filename):
        """Copy the new image to the fixed display_image.jpg file"""
        try:
            source_path = os.path.join(self.save_dir, new_image_filename)
            
            if not os.path.exists(source_path):
                print(f"? Source image not found: {source_path}")
                return False
            
            # Copy the new image to the fixed display filename
            shutil.copy2(source_path, self.display_image_path)
            
            old_source = self.current_display_source
            self.current_display_source = new_image_filename
            
            print(f"?? Updated display: {old_source} ? {new_image_filename}")
            print(f"?? Copied {new_image_filename} to display_image.jpg")
            
            return True
            
        except Exception as e:
            print(f"? Error updating display image: {e}")
            return False
    
    def cache_original_frame(self, appsink_original):
        """Cache original frame from the original video stream"""
        try:
            sample = appsink_original.emit("pull-sample")
            if sample is None:
                return Gst.FlowReturn.OK
                
            buffer = sample.get_buffer()
            caps = sample.get_caps()
            
            success, map_info = buffer.map(Gst.MapFlags.READ)
            if not success:
                return Gst.FlowReturn.OK
                
            try:
                structure = caps.get_structure(0)
                width = structure.get_int("width")[1]
                height = structure.get_int("height")[1]
                
                # Convert to numpy array
                frame_data = np.frombuffer(map_info.data, dtype=np.uint8)
                
                # Handle different formats
                format_str = structure.get_string("format")
                if format_str == "YUY2":
                    # YUY2 format - 2 bytes per pixel
                    yuy2_frame = frame_data.reshape((height, width, 2))
                    # Convert YUY2 to BGR
                    bgr_frame = cv2.cvtColor(yuy2_frame, cv2.COLOR_YUV2BGR_YUY2)
                elif format_str in ["RGBA", "RGBx"]:
                    # RGBA format - 4 bytes per pixel
                    rgba_frame = frame_data.reshape((height, width, 4))
                    bgr_frame = cv2.cvtColor(rgba_frame, cv2.COLOR_RGBA2BGR)
                elif format_str == "RGB":
                    # RGB format - 3 bytes per pixel
                    rgb_frame = frame_data.reshape((height, width, 3))
                    bgr_frame = cv2.cvtColor(rgb_frame, cv2.COLOR_RGB2BGR)
                else:
                    print(f"Unsupported format for original frame: {format_str}")
                    return Gst.FlowReturn.OK
                
                # Cache the frame thread-safely
                with self.cache_lock:
                    self.original_frame_cache = bgr_frame.copy()
                    
            finally:
                buffer.unmap(map_info)
            
            return Gst.FlowReturn.OK
            
        except Exception as e:
            print(f"Error caching original frame: {e}")
            return Gst.FlowReturn.OK
            
    def on_new_sample(self, appsink):
        """Process frames from appsink and count only persons"""
        try:
            # Pull sample from appsink
            sample = appsink.emit("pull-sample")
            if sample is None:
                return Gst.FlowReturn.OK
                
            # Get buffer and process
            buffer = sample.get_buffer()
            caps = sample.get_caps()
            
            success, map_info = buffer.map(Gst.MapFlags.READ)
            if not success:
                return Gst.FlowReturn.OK
                
            try:
                # Extract frame info
                structure = caps.get_structure(0)
                width = structure.get_int("width")[1]
                height = structure.get_int("height")[1]
                
                # Convert to numpy array
                frame_data = np.frombuffer(map_info.data, dtype=np.uint8)
                frame = frame_data.reshape((height, width, 4))  # RGBA
                
                # Count persons in the frame
                persons_detected = self.count_persons_in_frame(frame)
                
                self.frame_count += 1
                if persons_detected > 0:
                    self.total_persons_detected += persons_detected
                    print(f"Frame {self.frame_count}: {persons_detected} person(s) detected")
                    
                    # Save original frame if person detected
                    self.save_original_frame_if_needed(persons_detected)
                
                # Print stats every 30 frames
                if self.frame_count % 30 == 0:
                    print(f"=== PERSON DETECTION === Processed {self.frame_count} frames, "
                          f"total persons: {self.total_persons_detected}, "
                          f"saved images: {self.saved_images_count}")
                    
            finally:
                buffer.unmap(map_info)
            
            return Gst.FlowReturn.OK
            
        except Exception as e:
            print(f"Error in appsink callback: {e}")
            return Gst.FlowReturn.OK
    
    def save_original_frame_if_needed(self, persons_count):
        """Save original frame with circular buffer logic and update display"""
        try:
            current_time = datetime.now().timestamp()
            
            # Check 5-second delay requirement
            if current_time - self.last_save_time < self.save_interval:
                time_remaining = self.save_interval - (current_time - self.last_save_time)
                print(f"? Skipping save - {time_remaining:.1f}s remaining until next save allowed")
                return
            
            # Get cached original frame
            with self.cache_lock:
                if self.original_frame_cache is None:
                    print("? No original frame cached, skipping save")
                    return
                original_frame = self.original_frame_cache.copy()
            
            # Generate filename with circular buffer logic
            filename = f"image_{self.current_image_index}.jpg"
            filepath = os.path.join(self.save_dir, filename)
            
            # Check if we're overwriting an existing file
            is_overwrite = os.path.exists(filepath)
            
            # Save the original frame (without bounding boxes)
            success = cv2.imwrite(filepath, original_frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
            
            if success:
                self.saved_images_count += 1
                self.last_save_time = current_time
                
                if is_overwrite:
                    print(f"?? Overwritten {filename} ({persons_count} person(s)) - Total saves: {self.saved_images_count}")
                else:
                    print(f"?? Saved {filename} ({persons_count} person(s)) - Total saves: {self.saved_images_count}")
                
                # Update the display to show the newly saved image
                self.update_display_image(filename)
                
                # Update index for next save (circular: 1->2->3->4->5->1->2...)
                self.current_image_index += 1
                if self.current_image_index > self.max_images:
                    self.current_image_index = 1
                    print(f"?? Circular buffer full, next save will overwrite image_1")
                
                # Show current buffer status
                existing_files = []
                for i in range(1, self.max_images + 1):
                    test_path = os.path.join(self.save_dir, f"image_{i}.jpg")
                    if os.path.exists(test_path):
                        existing_files.append(f"image_{i}.jpg")
                
                print(f"?? Current buffer: [{', '.join(existing_files)}] - Next: image_{self.current_image_index}.jpg")
                
            else:
                print(f"? Failed to save frame: {filename}")
                
        except Exception as e:
            print(f"? Error saving original frame: {e}")
    
    def count_persons_in_frame(self, frame):
        """Count persons by analyzing bounding box overlays from tensor_decoder"""
        try:
            # Convert RGBA to BGR for processing
            bgr_frame = cv2.cvtColor(frame, cv2.COLOR_RGBA2BGR)
            
            # Method 1: Look for text labels containing "person"
            person_count_text = self.detect_person_labels(bgr_frame)
            
            # Method 2: Detect bounding boxes (as backup)
            person_count_boxes = self.detect_person_bounding_boxes(bgr_frame)
            
            # Use the higher count (more reliable detection)
            person_count = max(person_count_text, person_count_boxes)
            
            return min(person_count, 10)  # Cap at 10 to avoid false positives
            
        except Exception as e:
            print(f"Error in count_persons_in_frame: {e}")
            return 0
    
    def detect_person_labels(self, bgr_frame):
        """Detect 'person' text labels drawn by tensor_decoder"""
        try:
            # Convert to grayscale for text detection
            gray = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2GRAY)
            
            # Look for high contrast areas that might contain text
            _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
            
            # Find contours that might be text
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            person_count = 0
            for contour in contours:
                x, y, w, h = cv2.boundingRect(contour)
                
                # Filter for text-like dimensions (small rectangular areas)
                if 20 < w < 100 and 10 < h < 30:
                    # Extract the region
                    text_region = gray[y:y+h, x:x+w]
                    
                    # Simple check for text-like patterns
                    if self.looks_like_person_text(text_region):
                        person_count += 1
            
            return person_count
            
        except Exception as e:
            print(f"Error in detect_person_labels: {e}")
            return 0
    
    def looks_like_person_text(self, text_region):
        """Simple heuristic to check if a region might contain "person" text"""
        try:
            # Check if the region has the right characteristics for text
            if text_region.size == 0:
                return False
                
            # Look for horizontal lines (typical in text)
            horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 1))
            horizontal_lines = cv2.morphologyEx(text_region, cv2.MORPH_OPEN, horizontal_kernel)
            
            # Count non-zero pixels (text pixels)
            text_pixels = cv2.countNonZero(horizontal_lines)
            total_pixels = text_region.size
            
            # If 10-50% of pixels are text-like, it might be a label
            text_ratio = text_pixels / total_pixels
            return 0.1 < text_ratio < 0.5
            
        except:
            return False
    
    def detect_person_bounding_boxes(self, bgr_frame):
        """Detect rectangular bounding boxes that might represent persons"""
        try:
            # Convert to HSV for better color detection
            hsv = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2HSV)
            
            # Look for typical bounding box colors (bright colors)
            lower_bound1 = np.array([0, 100, 100])    # Red range
            upper_bound1 = np.array([10, 255, 255])
            lower_bound2 = np.array([170, 100, 100])  # Red range (wrap around)
            upper_bound2 = np.array([180, 255, 255])
            
            # Create masks for potential bounding box colors
            mask1 = cv2.inRange(hsv, lower_bound1, upper_bound1)
            mask2 = cv2.inRange(hsv, lower_bound2, upper_bound2)
            mask = cv2.bitwise_or(mask1, mask2)
            
            # Find contours
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            person_count = 0
            for contour in contours:
                # Get bounding rectangle
                x, y, w, h = cv2.boundingRect(contour)
                
                # Filter for person-like bounding boxes
                aspect_ratio = float(w) / h
                area = w * h
                
                # Person bounding boxes are typically taller than wide
                if (0.3 < aspect_ratio < 0.8 and  # Taller than wide
                    area > 2000 and              # Minimum size
                    w > 30 and h > 50):          # Minimum dimensions
                    
                    # Additional check: look for box-like structure
                    if self.is_bounding_box_shape(contour):
                        person_count += 1
            
            return person_count
            
        except Exception as e:
            print(f"Error in detect_person_bounding_boxes: {e}")
            return 0
    
    def is_bounding_box_shape(self, contour):
        """Check if contour looks like a bounding box (rectangular)"""
        try:
            # Approximate contour to polygon
            epsilon = 0.02 * cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, epsilon, True)
            
            # Bounding boxes should have 4 corners (rectangular)
            return len(approx) >= 4
            
        except:
            return False


class PersonDetectionPipeline:
    def __init__(self, camera_path, model_path, labels_path, boxes_path):
        """Initialize the person detection pipeline with configurable parameters"""
        
        # Set environment variables
        os.environ['LIBCAMERA_PIPELINES_MATCH_LIST'] = 'nxp/neo,imx8-isi'
        os.environ['LIBCAMERA_IPA_MODULE_PATH'] = '/usr/lib/libcamera/ipa-nxp-neo-uguzzi'
        os.environ['LIBCAMERA_LOG_LEVELS'] = 'NxpNeoPipe:ERROR,NxpNeoIsiDev:ERROR,NxpNeoDev:ERROR'

        # Configuration from GUI
        self.camera_path = camera_path
        self.model_path = model_path
        self.labels_path = labels_path
        self.boxes_path = boxes_path
        
        # Create directory for saved images
        self.save_dir = "/root/4k_demo/"
        os.makedirs(self.save_dir, exist_ok=True)
        
        # Initialize detection handler
        self.detection_handler = PersonDetectionHandler(
            self.save_dir, 
            self.labels_path
        )
        
        # Pipeline components
        self.main_pipeline = None
        self.loop = None
        self.running = False

    def create_pipelines(self):
        """Create the main and image pipelines"""
        try:
            # Create default display image
            self.create_default_display_image()
            
            # Create image pipeline
            if not self.detection_handler.create_image_pipeline():
                print("? Failed to create image pipeline")
                return False
            
            # Main pipeline string
            pipeline_str = f"""
            imxcompositor_g2d name=mix sink_0::zorder=1 sink_1::zorder=2 sink_2::zorder=3 
                sink_2::xpos=2880 sink_2::ypos=1620 sink_2::width=960 sink_2::height=540 
            libcamerasrc camera-name="{self.camera_path}" ! 
            video/x-raw,format=YUY2,framerate=5/1 ! 
            queue max-size-buffers=3 leaky=downstream ! 
            tee name=main_tee 
                main_tee. ! queue name=thread-nn max-size-buffers=1 leaky=downstream ! 
                           imxvideoconvert_g2d ! 
                           video/x-raw,width=300,height=300,format=RGBA ! 
                           videoconvert ! 
                           video/x-raw,format=RGB ! 
                           tensor_converter ! 
                           tensor_filter name=model_inference 
                               framework=tensorflow-lite 
                               model={self.model_path} 
                               custom=Delegate:XNNPACK,NumThreads=5 ! 
                           tensor_decoder 
                               mode=bounding_boxes 
                               option1=mobilenet-ssd 
                               option2={self.labels_path} 
                               option3={self.boxes_path} 
                               option4=3840:2160 
                               option5=300:300 
                               option6=0.3 ! 
                           imxvideoconvert_g2d ! 
                           video/x-raw,format=RGBA ! 
                           tee name=processed_tee 
                               processed_tee. ! queue max-size-buffers=2 leaky=downstream ! mix.sink_1 
                               processed_tee. ! queue max-size-buffers=1 leaky=downstream ! 
                                   appsink name=detection_sink 
                                       emit-signals=true 
                                       max-buffers=2 
                                       drop=true 
                                       sync=false 
                                       async=false 
                                       caps=video/x-raw,format=RGBA
                main_tee. ! tee name=original_tee 
                           original_tee. ! queue name=thread-original max-size-buffers=2 leaky=downstream ! 
                                          videoconvert ! 
                                          mix.sink_0 
                           original_tee. ! queue max-size-buffers=1 leaky=downstream ! 
                                          appsink name=original_sink 
                                              emit-signals=true 
                                              max-buffers=1 
                                              drop=true 
                                              sync=false 
                                              async=false 
                                              caps=video/x-raw,format=YUY2
            intervideosrc channel=image_channel ! 
            video/x-raw,format=RGBA,width=960,height=540,framerate=5/1 ! 
            queue max-size-buffers=1 leaky=downstream ! 
            mix.sink_2
            mix. ! waylandsink sync=false
            """
            
            # Create main pipeline
            self.main_pipeline = Gst.parse_launch(pipeline_str)
            self.detection_handler.main_pipeline = self.main_pipeline
            
            # Connect appsink callbacks
            appsink = self.main_pipeline.get_by_name("detection_sink")
            if appsink:
                appsink.connect("new-sample", self.detection_handler.on_new_sample)
                print("Connected person detection appsink callback")
            else:
                print("Error: Could not find detection appsink element")
                return False

            original_appsink = self.main_pipeline.get_by_name("original_sink")
            if original_appsink:
                original_appsink.connect("new-sample", self.detection_handler.cache_original_frame)
                print("Connected original frame caching appsink callback")
            else:
                print("Error: Could not find original appsink element")
                return False

            # Set up bus
            bus = self.main_pipeline.get_bus()
            bus.add_signal_watch()
            bus.connect("message", self.on_message)
            
            return True
            
        except Exception as e:
            print(f"Error creating pipelines: {e}")
            return False

    def create_default_display_image(self):
        """Create a default display image"""
        default_image_path = os.path.join(self.save_dir, "image_1.jpg")
        
        if not os.path.exists(default_image_path):
            # Create a simple black image with text
            img = np.zeros((540, 960, 3), dtype=np.uint8)
            cv2.putText(img, "No Recent Images", (320, 250), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            cv2.putText(img, "Waiting for person detection...", (240, 300), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 2)
            cv2.imwrite(default_image_path, img)
            print(f"?? Created default image: {default_image_path}")
        
        # Copy to the display image file
        shutil.copy2(default_image_path, self.detection_handler.display_image_path)
        print(f"?? Created display image: {self.detection_handler.display_image_path}")

    def on_message(self, bus, message):
        """Handle GStreamer bus messages"""
        if message.type == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            print(f"Pipeline Error: {err}")
            if self.loop:
                self.loop.quit()
            return False
        elif message.type == Gst.MessageType.EOS:
            print("End of stream reached")
            if self.loop:
                self.loop.quit()
            return False
        elif message.type == Gst.MessageType.WARNING:
            warn, debug = message.parse_warning()
            if "frame loss" not in str(warn).lower():
                print(f"Pipeline Warning: {warn}")
        return True

    def print_stats(self):
        """Print statistics"""
        existing_files = []
        for i in range(1, self.detection_handler.max_images + 1):
            test_path = os.path.join(self.save_dir, f"image_{i}.jpg")
            if os.path.exists(test_path):
                existing_files.append(f"image_{i}")
        
        print(f"=== STATS === Frames: {self.detection_handler.frame_count}, "
              f"Persons: {self.detection_handler.total_persons_detected}, "
              f"Saves: {self.detection_handler.saved_images_count}, "
              f"Buffer: [{', '.join(existing_files)}], "
              f"Next: image_{self.detection_handler.current_image_index}, "
              f"Display: {self.detection_handler.current_display_source}")
        return True

    def run(self):
        """Run the person detection pipeline"""
        try:
            print(f"Creating person detection pipeline...")
            print(f"Camera: {self.camera_path}")
            print(f"Model: {self.model_path}")
            print(f"Labels: {self.labels_path}")
            print(f"Boxes: {self.boxes_path}")
            print(f"Save directory: {self.save_dir}")
            
            # Create pipelines
            if not self.create_pipelines():
                print("Failed to create pipelines")
                return
            
            # Start image pipeline first
            print("Starting image pipeline...")
            ret = self.detection_handler.image_pipeline.set_state(Gst.State.PLAYING)
            if ret == Gst.StateChangeReturn.FAILURE:
                print("Failed to start image pipeline")
                return
            
            # Start main pipeline
            print("Starting main pipeline...")
            ret = self.main_pipeline.set_state(Gst.State.PLAYING)
            if ret == Gst.StateChangeReturn.FAILURE:
                print("Failed to start main pipeline")
                return
            
            # Create main loop
            self.loop = GLib.MainLoop()
            self.running = True
            
            # Set up timers
            GLib.timeout_add_seconds(5, self.print_stats)
            GLib.timeout_add_seconds(int(self.detection_handler.image_reload_interval), 
                                   self.detection_handler.restart_image_pipeline)
            
            print("Person detection pipeline running...")
            print("- Circular buffer saves last 5 images with person detection")
            print("- Minimum 5 seconds between saves")
            print("- Image pipeline restarts every 3 seconds")
            
            # Run the main loop
            self.loop.run()
            
        except Exception as e:
            print(f"Error running pipeline: {e}")
        finally:
            self.stop()

    def stop(self):
        """Stop the person detection pipeline"""
        print("Stopping person detection pipeline...")
        self.running = False
        
        if self.loop and self.loop.is_running():
            self.loop.quit()
        
        if self.detection_handler.image_pipeline:
            self.detection_handler.image_pipeline.set_state(Gst.State.NULL)
        
        if self.main_pipeline:
            self.main_pipeline.set_state(Gst.State.NULL)
        
        # Show final statistics
        existing_files = []
        for i in range(1, self.detection_handler.max_images + 1):
            test_path = os.path.join(self.save_dir, f"image_{i}.jpg")
            if os.path.exists(test_path):
                existing_files.append(f"image_{i}.jpg")
        
        print(f"\n=== FINAL STATISTICS ===")
        print(f"Frames processed: {self.detection_handler.frame_count}")
        print(f"Total PERSONS detected: {self.detection_handler.total_persons_detected}")
        print(f"Total saves performed: {self.detection_handler.saved_images_count}")
        print(f"Final buffer state: [{', '.join(existing_files)}]")
        print(f"Latest image displayed: {self.detection_handler.current_display_source}")
        print(f"Images saved to: {self.save_dir}")
        print("Pipeline stopped successfully")


class NNStreamerLauncher:
    """The GUI window for the Object Detection example launcher"""

    def __init__(self):
        """Creates the UI window"""

        # Obtain GUI settings and configurations
        glade_file = (
            "/opt/gopoint-apps/scripts/machine_learning/nnstreamer/4k_Object_detection/4k_object_detection.glade"
        )
        self.builder = gtk.Builder()
        self.builder.add_from_file(glade_file)
        self.builder.connect_signals(self)

        # Create instances of widgets
        self.sources_list = self.builder.get_object("sources-list")
        self.backend_list = self.builder.get_object("backend-list")
        self.resolution_list = self.builder.get_object("resolution-list")
        self.color_list = self.builder.get_object("color-list")
        self.display_performance = self.builder.get_object("display-performance")
        self.start_button = self.builder.get_object("start-button")
        self.header_bar = self.builder.get_object("header-bar")
        self.status_bar = self.builder.get_object("status-bar")
        self.about_button = self.builder.get_object("about-button")
        self.about_dialog = self.builder.get_object("about-dialog")
        self.progress_bar = self.builder.get_object("progress-bar")
        self.close_button = self.builder.get_object("close-button")

        # Get platform
        self.platform = subprocess.check_output(
            ["cat", "/sys/devices/soc0/soc_id"]
        ).decode("utf-8")[:-1]

        # General variables
        self.labels = "coco_labels_list.txt"
        self.tflite_model = "ssdlite_mobilenet_v2_coco_no_postprocess.tflite"
        self.npu_tflite_model = (
            "ssdlite_mobilenet_v2_coco_quant_uint8_float32_no_postprocess.tflite"
        )
        self.neutron_tflite_model = "ssdlite_mobilenet_v2_coco_quant_uint8_float32_no_postprocess_neutron.tflite"
        self.vela_tflite_model = (
            MODELS_PATH
            + "ssdlite_mobilenet_v2_coco_quant_uint8_float32_no_postprocess_vela.tflite"
        )
        self.boxes_file = "box_priors.txt"

        # Progress bar config
        self.pulsing = False
        self.timeout_id = None
        self.progress_bar.set_show_text(False)

        # Get main application window
        window = self.builder.get_object("main-window")

        # Main process for nnstreamer example
        self.output_process = None
        
        # Person detection pipeline instance
        self.person_detection_pipeline = None

        # OpenVX graph caching is not available on i.MX 8QuadMax platform.
        if self.platform == "i.MX8MP":
            os.environ["VIV_VX_CACHE_BINARY_GRAPH_DIR"] = "/opt/gopoint-apps/downloads"
            os.environ["VIV_VX_ENABLE_CACHE_GRAPH_BINARY"] = "1"

        # Obtain available devices
        import re  # Ensure re is imported
        # Obtain available devices
        devices = []
        try:
            cam_output = subprocess.check_output(['cam', '-l']).decode('utf-8')
            matches = re.findall(r"'os08a20' \((.*?)\)", cam_output)
            for i, match in enumerate(matches):
                device_label = f"os08a20:{match}"
                self.sources_list.append_text(device_label)
                devices.append(device_label)
            if devices:
                self.sources_list.set_active(0)
            else:
                raise ValueError("No os08a20 cameras found")
        except Exception as e:
            print(f"Error detecting os08a20 cameras: {e}")
            for device in glob.glob("/dev/video*"):
                self.sources_list.append_text(device)
                devices.append(device)
            if devices:
                self.sources_list.set_active(0)

        if (
            self.platform in ("i.MX8MP", "i.MX8MM", "i.MX8QM")
            and "/dev/video3" in devices
        ):
            self.sources_list.set_active(3)

        # Populate backends
        backends = []
        if self.platform in ("i.MX93", "i.MX95", "i.MX8MP"):
            backends.append("NPU")
        backends.append("CPU")
        for backend in backends:
            self.backend_list.append_text(backend)
        # Add GPU option for i.MX8
        if self.platform in ("i.MX8MP", "i.MX8MN", "i.MX8QM", "i.MX95"):
            self.backend_list.append_text("GPU")
        self.backend_list.set_active(0)

        # Populate resolution for video
        resolutions = ["1920x1080", "3840x2160"]
        for resolution in resolutions:
            self.resolution_list.append_text(resolution)
        self.resolution_list.set_active(1)

        colors = ["white", "red", "green", "blue", "black"]
        for color in colors:
            self.color_list.append_text(color)
        self.color_list.set_active(0)

        self.close_button.connect("clicked", self.quit_app)
        window.connect("delete-event", gtk.main_quit)
        window.show()

        # Preload model
        preload_thread = threading.Thread(target=self.preload, daemon=True)
        preload_thread.start()

    def quit_app(self, widget):
        """Closes GTK+3 GUI and kills NNStreamer process"""
        if self.output_process:
            self.output_process.kill()
        
        # Stop person detection pipeline if running
        if self.person_detection_pipeline:
            self.person_detection_pipeline.stop()
            
        gtk.main_quit()

    def about_button_activate(self, widget):
        """
        Function to handle about dialog window
        """
        self.about_dialog.run()
        time.sleep(1)
        self.about_dialog.hide()
        return True

    def on_timeout(self):
        """
        Function to handle progress bar
        """
        if self.pulsing:
            self.progress_bar.set_show_text(True)
            self.progress_bar.pulse()
            return True
        self.progress_bar.set_show_text(False)
        self.progress_bar.set_fraction(0.0)
        return False

    def compile_vela(self):
        """Compile vela models"""
        if not os.path.exists(self.vela_tflite_model):
            GLib.idle_add(
                self.status_bar.set_text,
                "Compiling model with vela and saving to cache...",
            )

            subprocess.run(
                "vela "
                + self.npu_tflite_model
                + " --output-dir=/opt/gopoint-apps/downloads/",
                shell=True,
                check=True,
            )

    def preload(self):
        """Download the models, compile the models and setup default configuration"""

        # Block run button and start progress bar
        self.unblock_buttons(False)
        self.pulsing = True
        self.timeout_id = GLib.timeout_add(50, self.on_timeout)

        GLib.idle_add(self.status_bar.set_text, "Downloading CPU model...")
        self.tflite_model = utils.download_file(self.tflite_model)

        # Verify if download is successfull
        if self.tflite_model == -1:
            GLib.idle_add(
                self.status_bar.set_text,
                "Cannot find files!\n"
                "Make sure required files are available in downloads database!",
            )
            self.pulsing = False
            self.unblock_buttons(True)
            return
        if self.tflite_model == -2:
            GLib.idle_add(
                self.status_bar.set_text,
                "Download failed!\n"
                "Please make sure you have internet connection on the target and try again.",
            )
            self.pulsing = False
            self.unblock_buttons(True)
            return
        if self.tflite_model == -3:
            GLib.idle_add(
                self.status_bar.set_text,
                "Downloaded corrupted file!\n"
                "Please clean /opt/gopoint-apps/downloads and try to download again.",
            )
            self.pulsing = False
            self.unblock_buttons(True)
            return

        GLib.idle_add(self.status_bar.set_text, "CPU model successfully downloaded!")

        GLib.idle_add(self.status_bar.set_text, "Downloading NPU model...")
        self.npu_tflite_model = utils.download_file(self.npu_tflite_model)

        # Verify if download is successfull
        if self.npu_tflite_model == -1:
            GLib.idle_add(
                self.status_bar.set_text,
                "Cannot find files!\n"
                "Make sure required files are available in downloads database!",
            )
            self.pulsing = False
            self.unblock_buttons(True)
            return
        if self.npu_tflite_model == -2:
            GLib.idle_add(
                self.status_bar.set_text,
                "Download failed!\n"
                "Please make sure you have internet connection on the target and try again.",
            )
            self.pulsing = False
            self.unblock_buttons(True)
            return
        if self.npu_tflite_model == -3:
            GLib.idle_add(
                self.status_bar.set_text,
                "Downloaded corrupted file!\n"
                "Please clean /opt/gopoint-apps/downloads and try to download again.",
            )
            self.pulsing = False
            self.unblock_buttons(True)
            return

        GLib.idle_add(self.status_bar.set_text, "NPU model successfully downloaded!")

        if self.platform == "i.MX95":
            GLib.idle_add(self.status_bar.set_text, "Downloading NPU model...")

            self.neutron_tflite_model = utils.download_file(self.neutron_tflite_model)

            # Verify if download is successfull
            if self.neutron_tflite_model == -1:
                GLib.idle_add(
                    self.status_bar.set_text,
                    "Cannot find files!\n"
                    "Make sure required files are available in downloads database!",
                )
                self.pulsing = False
                self.unblock_buttons(True)
                return
            if self.neutron_tflite_model == -2:
                GLib.idle_add(
                    self.status_bar.set_text,
                    "Download failed!\n"
                    "Please make sure you have internet connection on the target and try again.",
                )
                self.pulsing = False
                self.unblock_buttons(True)
                return
            if self.neutron_tflite_model == -3:
                GLib.idle_add(
                    self.status_bar.set_text,
                    "Downloaded corrupted file!\n"
                    "Please clean /opt/gopoint-apps/downloads and try to download again.",
                )
                self.pulsing = False
                self.unblock_buttons(True)
                return

            GLib.idle_add(self.status_bar.set_text, "NPU model successfully downloaded!")

        GLib.idle_add(self.status_bar.set_text, "Downloading labels...")
        self.labels = utils.download_file(self.labels)

        # Verify if download is successfull
        if self.labels == -1:
            GLib.idle_add(
                self.status_bar.set_text,
                "Cannot find files!\n"
                "Make sure required files are available in downloads database!",
            )
            self.pulsing = False
            self.unblock_buttons(True)
            return
        if self.labels == -2:
            GLib.idle_add(
                self.status_bar.set_text,
                "Download failed!\n"
                "Please make sure you have internet connection on the target and try again.",
            )
            self.pulsing = False
            self.unblock_buttons(True)
            return
        if self.labels == -3:
            GLib.idle_add(
                self.status_bar.set_text,
                "Downloaded corrupted file!\n"
                "Please clean /opt/gopoint-apps/downloads and try to download again.",
            )
            self.pulsing = False
            self.unblock_buttons(True)
            return

        GLib.idle_add(self.status_bar.set_text, "Labels successfully downloaded!")

        GLib.idle_add(self.status_bar.set_text, "Downloading box priors...")
        self.boxes_file = utils.download_file(self.boxes_file)

        # Verify if download is successfull
        if self.boxes_file == -1:
            GLib.idle_add(
                self.status_bar.set_text,
                "Cannot find files!\n"
                "Make sure required files are available in downloads database!",
            )
            self.pulsing = False
            self.unblock_buttons(True)
            return
        if self.boxes_file == -2:
            GLib.idle_add(
                self.status_bar.set_text,
                "Download failed!\n"
                "Please make sure you have internet connection on the target and try again.",
            )
            self.pulsing = False
            self.unblock_buttons(True)
            return
        if self.boxes_file == -3:
            GLib.idle_add(
                self.status_bar.set_text,
                "Downloaded corrupted file!\n"
                "Please clean /opt/gopoint-apps/downloads and try to download again.",
            )
            self.pulsing = False
            self.unblock_buttons(True)
            return

        GLib.idle_add(self.status_bar.set_text, "Box priors successfully downloaded!")

        # Compile model using vela tool for i.MX 93
        if self.platform == "i.MX93":
            self.compile_vela()

        # If i.MX 8M PLus, pre-run model to avoid warmup time during execution
        if self.platform == "i.MX8MP":
            GLib.idle_add(
                self.status_bar.set_text,
                "Warming up model and saving to cache...",
            )

            subprocess.run(
                "/usr/bin/tensorflow-lite-*/examples/benchmark_model "
                "--graph="
                + self.npu_tflite_model
                + " --external_delegate_path=/usr/lib/libvx_delegate.so",
                shell=True,
                check=True,
            )

        self.pulsing = False
        GLib.idle_add(self.status_bar.set_text, "Application is ready!")
        self.unblock_buttons(True)
        self.resolution_list.set_sensitive(False)

    def unblock_buttons(self, status):
        """Block/unblock buttons"""
        self.start_button.set_sensitive(status)
        self.sources_list.set_sensitive(status)
        self.backend_list.set_sensitive(status)
        self.resolution_list.set_sensitive(status)
        self.color_list.set_sensitive(status)
        self.display_performance.set_sensitive(status)

    def get_camera_path_from_device(self, device):
        """Convert device label to camera path"""
        if "os08a20:" in device:
            # Extract the path from the device label
            camera_path = device.replace("os08a20:", "")
            return camera_path
        else:
            # For video devices, we need to map to camera path
            # This is a simplified mapping - you may need to adjust based on your system
            if device == "/dev/video0":
                return "/base/soc/bus@42000000/i2c@42530000/os08a20_mipi@36"
            elif device == "/dev/video3":
                return "/base/soc/bus@44000000/i2c@44350000/os08a20_mipi@36"
            else:
                # Default camera path
                return "/base/soc/bus@42000000/i2c@42530000/os08a20_mipi@36"

    @threaded
    def start(self, widget):
        """Start the person detection pipeline"""
        self.unblock_buttons(False)

        GLib.idle_add(
            self.status_bar.set_text,
            "Starting Person Detection Pipeline...",
        )

        # Get options from user
        device = self.sources_list.get_active_text()
        backend = self.backend_list.get_active_text()
        color = self.color_list.get_active_text()
        performance_display = self.display_performance.get_active()

        # Configure arguments
        model = self.npu_tflite_model
        if backend in ("GPU"):
            model = self.tflite_model
        if self.platform == "i.MX95" and backend == "NPU":
            model = self.neutron_tflite_model
        if backend == "NPU" and self.platform == "i.MX93":
            model = self.vela_tflite_model

        # Convert device to camera path
        camera_path = self.get_camera_path_from_device(device)

        print(f"Starting person detection with:")
        print(f"  Device: {device}")
        print(f"  Camera Path: {camera_path}")
        print(f"  Backend: {backend}")
        print(f"  Model: {model}")
        print(f"  Labels: {self.labels}")
        print(f"  Boxes: {self.boxes_file}")

        try:
            # Create and start the person detection pipeline
            self.person_detection_pipeline = PersonDetectionPipeline(
                camera_path=camera_path,
                model_path=model,
                labels_path=self.labels,
                boxes_path=self.boxes_file
            )

            # Start the pipeline in a separate thread
            pipeline_thread = threading.Thread(
                target=self.person_detection_pipeline.run,
                daemon=True
            )
            pipeline_thread.start()

            GLib.idle_add(
                self.status_bar.set_text,
                "Person Detection Pipeline Running! Check terminal for stats.",
            )

        except Exception as e:
            print(f"Error starting person detection pipeline: {e}")
            GLib.idle_add(
                self.status_bar.set_text,
                f"Error starting pipeline: {str(e)}",
            )
            self.unblock_buttons(True)

        return True


if __name__ == "__main__":
    print("Starting NXP Object Detection GUI with Person Detection Pipeline")
    print("Features:")
    print("- GUI for selecting camera, backend, and model settings")
    print("- Person detection with circular buffer image saving")
    print("- Real-time display with bounding boxes")
    print("- Saved images displayed in bottom-right corner")
    print("- Automatic image rotation every 3 seconds")
    print("- 5-second minimum interval between saves")
    print("- Saves last 5 images with person detection")
    
    win = NNStreamerLauncher()
    gtk.main()
