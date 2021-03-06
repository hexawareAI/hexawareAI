## USAGE
# python webstreaming.py --ip 192.168.29.251 --port 8000

# import the necessary packages
# from pyimagesearch.motion_detection import SingleMotionDetector
from imutils.video import VideoStream
from flask import Response
from flask import Flask
from flask import render_template
import threading
import argparse
import datetime
import imutils
import time
import dlib
import os
import cv2
import numpy as np
from yolo_helper import YoloV3, load_darknet_weights, draw_outputs
from dlib_helper import (shape_to_np,
                         eye_on_mask,
                         contouring,
                         process_thresh,
                         print_eye_pos,
                         nothing)

from define_mouth_distances import return_distances
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
yolo = YoloV3()
load_darknet_weights(yolo, 'yolov3.weights')
detector = dlib.get_frontal_face_detector()
predictor = dlib.shape_predictor('shape_68.dat')

d_outer, d_inner = return_distances(detector, predictor)
cap =  cv2.VideoCapture(0)  #VideoStream(src=0).start()
print(cap.read())
_, frame_size = cap.read()

# initialize a flask object
app = Flask(__name__)

# initialize the video stream and allow the camera sensor to
# warmup
# vs = VideoStream(usePiCamera=1).start()
# vs = VideoStream(src=0).start()
# time.sleep(2.0)

@app.route("/")
def index():
	# return the rendered template
	return render_template("index.html")

def eyes_mouth():

    ret, img = cap.read()
    thresh = img.copy()
    w, h = img.shape[:2]
    outer_points = [[49, 59], [50, 58], [51, 57], [52, 56], [53, 55]]
    inner_points = [[61, 67], [62, 66], [63, 65]]
    left = [36, 37, 38, 39, 40, 41]
    right = [42, 43, 44, 45, 46, 47]
    kernel = np.ones((9, 9), np.uint8)
    cv2.namedWindow('image')
    cv2.createTrackbar('threshold', 'image', 0, 255, nothing)


    while True:
        ret, img = cap.read()
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        rects = detector(gray, 1)

        for rect in rects:
            shape = predictor(gray, rect)
            shape = shape_to_np(shape)

            #mouth
            cnt_outer = 0
            cnt_inner = 0
            for i, (p1, p2) in enumerate(outer_points):
                if d_outer[i] + 5 < shape[p2][1] - shape[p1][1]:
                    cnt_outer += 1
            for i, (p1, p2) in enumerate(inner_points):
                if d_inner[i] + 3 < shape[p2][1] - shape[p1][1]:
                    cnt_inner += 1
            if cnt_outer > 3 or cnt_inner > 2:
                print('Mouth open')
            for (x, y) in shape[48:]:
                cv2.circle(img, (x, y), 2, (0, 0, 255), -1)

            #eyes
            mask = np.zeros((w, h), dtype=np.uint8)
            mask, end_points_left = eye_on_mask(mask, left, shape)
            mask, end_points_right = eye_on_mask(mask, right, shape)
            mask = cv2.dilate(mask, kernel, 5)
            eyes = cv2.bitwise_and(img, img, mask=mask)
            mask = (eyes == [0, 0, 0]).all(axis=2)
            eyes[mask] = [255, 255, 255]
            mid = (shape[42][0] + shape[39][0]) // 2
            eyes_gray = cv2.cvtColor(eyes, cv2.COLOR_BGR2GRAY)
            threshold = cv2.getTrackbarPos('threshold', 'image')
            _, thresh = cv2.threshold(eyes_gray, threshold, 255, cv2.THRESH_BINARY)
            thresh = process_thresh(thresh)
            eyeball_pos_left = contouring(thresh[:, 0:mid], mid, img, end_points_left)
            eyeball_pos_right = contouring(thresh[:, mid:], mid, img, end_points_right, True)
            print_eye_pos(eyeball_pos_left, eyeball_pos_right)

        cv2.imshow('result', img)
        cv2.imshow("image", thresh)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

def count_people_and_phones():
    while True:
        ret, image = cap.read()
        frame = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        frame = cv2.resize(frame, (320, 320))
        frame = frame.astype(np.float32)
        frame = np.expand_dims(frame, 0)
        frame = frame / 255
        class_names = [c.strip() for c in open("classes.txt").readlines()]
        boxes, scores, classes, nums = yolo(frame)
        count = 0
        for i in range(nums[0]):
            if int(classes[0][i] == 0):
                count += 1
            if int(classes[0][i] == 67):
                print("Mobile Phone Detected")
        if count == 0:
            print('No person detected')
        elif count > 1:
            print('More than one person detected')
        image = draw_outputs(image, (boxes, scores, classes, nums), class_names)
        cv2.imshow('Prediction', image)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break


# @app.route("/video_feed")
# def video_feed():
# 	# return the response generated along with the specific media
# 	# type (mime type)
# 	return Response(generate(),
# 		mimetype = "multipart/x-mixed-replace; boundary=frame")

# check to see if this is the main thread of execution
if __name__ == '__main__':
	# construct the argument parser and parse command line arguments
	ap = argparse.ArgumentParser()
	ap.add_argument("-i", "--ip", type=str, required=True,
		help="ip address of the device")
	ap.add_argument("-o", "--port", type=int, required=True,
		help="ephemeral port number of the server (1024 to 65535)")
	ap.add_argument("-f", "--frame-count", type=int, default=32,
		help="# of frames used to construct the background model")
	args = vars(ap.parse_args())

	# start a thread that will perform motion detection
	t1 = threading.Thread(target=eyes_mouth)
	t2 = threading.Thread(target=count_people_and_phones)
	t1.start()
	t2.start()
	t1.join()
	t2.join()

	# start the flask app
	app.run(host=args["ip"], port=args["port"], debug=True,
		threaded=True, use_reloader=False)

	# app.run(debug=True, threaded=True, use_reloader=False)

# release the video stream pointer
cap.release()
cv2.destroyAllWindows()