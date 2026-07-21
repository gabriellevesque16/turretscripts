import cv2
import numpy as np
import os
import keyboard

    # Define paths to the files
CONFIG_PATH = r"C:\Users\gabri\source\VSC projects\pew\getgood\yolov3.cfg"
WEIGHTS_PATH = r"C:\Users\gabri\source\VSC projects\pew\getgood\yolov3.weights"
CLASSES_PATH = r"C:\Users\gabri\source\VSC projects\pew\getgood\yolov3.txt"

# Verify all required files exist
for path in [CONFIG_PATH, WEIGHTS_PATH, CLASSES_PATH]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")

# Load class names
with open(CLASSES_PATH, 'r') as f:
    classes = [line.strip() for line in f.readlines()]

# Generate random colors for each class
COLORS = np.random.uniform(0, 255, size=(len(classes), 3))

# Load YOLO model
net = cv2.dnn.readNet(WEIGHTS_PATH, CONFIG_PATH)

#Load camera
cap = cv2.VideoCapture(0)

try:
  while True:
# Load image
    _, image = cap.read()
    Height, Width = image.shape[:2]

# Create blob
    blob = cv2.dnn.blobFromImage(image, 0.00392, (416, 416), swapRB=True, crop=False)
    net.setInput(blob)

# Get output layer names
    def get_output_layers(net):
       layer_names = net.getLayerNames()
       return [layer_names[i - 1] for i in net.getUnconnectedOutLayers().flatten()]

    outs = net.forward(get_output_layers(net))

# Initialize lists for detection results
    class_ids, confidences, boxes = [], [], []

# Process detections
    for out in outs:
        for detection in out:
            scores = detection[5:]
            class_id = np.argmax(scores)
            confidence = scores[class_id]
            if confidence > 0.5:
                center_x, center_y, width, height = (detection[0:4] * np.array([Width, Height, Width, Height])).astype("int")
                x, y = int(center_x - width / 2), int(center_y - height / 2)
                boxes.append([x, y, int(width), int(height)])
                confidences.append(float(confidence))
                class_ids.append(class_id)

# Apply non-max suppression to remove duplicate bounding boxes
    indices = cv2.dnn.NMSBoxes(boxes, confidences, 0.5, 0.4)

    if len(indices) > 0:  # Check if there are detections
        indices = indices.flatten()  # Convert to a list

        for i in indices:
            x, y, w, h = boxes[i]
            label = f"{classes[class_ids[i]]}: {confidences[i]:.2f}"
            color = COLORS[class_ids[i]]
            cv2.rectangle(image, (x, y), (x + w, y + h), color, 2)
            cv2.putText(image, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

# Show detected objects
    key = cv2.waitKey(1)
    
    if keyboard.is_pressed('q'):
            break

finally:
    cap.release()
    cv2.destroyAllWindows()


     
