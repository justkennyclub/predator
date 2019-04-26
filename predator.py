from imutils.video import VideoStream
import imutils
from flask import Flask, render_template, redirect, request, flash
#for processing pre-recorded video, hmm actually applicable to both
import cv2, time, pandas
from datetime import datetime

from werkzeug import secure_filename
import os

from bokeh.plotting import figure, show, output_file, reset_output
from bokeh.models import HoverTool, ColumnDataSource

ALLOWED_EXTENSIONS = set(['mp4'])
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

UPLOAD_FOLDER = './'
app = Flask(__name__)
app.secret_key = b'_5#y2L"F4Q8z\n\xec]/' #for using flash
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


@app.route('/')
def index():
    return render_template("index.html")

@app.route('/processing', methods = ['GET', 'POST'])
def processing():
    filename=''
    show_delta = show_threshold = show_gray = False
    if request.method == 'POST':
        if (request.form.get('delta')):
            show_delta = True
        if (request.form.get('threshold')):
            show_threshold = True
        if (request.form.get('gray')):
            show_gray = True
      
        if 'option_webcam' in request.form:
            filename = 0
        else:
            # check if the post request has the file part
            if 'file' not in request.files:
                flash('No file part')
                return render_template("processing_error.html")
            file = request.files['file']
            # if user does not select file, browser also
            # submit a empty part without filename
            if file.filename == '':
                flash('No selected file')
                return render_template("processing_error.html")
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            else:
                abort(401)
                return render_template("processing_error.html")
           
    else:
        return redirect('/')
    
    print(filename)

    first_frame = None
    status_list = [None, None]
    times = []
    df = pandas.DataFrame(columns=["Enter", "Exit"])

    if filename==0:
        video = VideoStream(src=0).start()
        time.sleep(2.0)
    else:
        video = cv2.VideoCapture(filename)


    firstFrame = None

    #set result files locations
    photos_folder = './predture/'+datetime.now().strftime("%A_%d_%B_%Y_%I-%M-%S%p")
    if not os.path.isdir(photos_folder):
        os.mkdir(photos_folder)
    
    data_folder = './predture_data/'+datetime.now().strftime("%A_%d_%B_%Y_%I-%M-%S%p")
    if not os.path.isdir(data_folder):
        os.mkdir(data_folder)

    # loop over the frames of the video
    while True:
        # grab the current frame and initialize the occupied/unoccupied text
        frame = video.read()
        frame = frame if (filename==0) else frame[1]
        status = 0
        text="empty"
    
        #check if there is still frame left (if video is finished)       
        # if the frame could not be grabbed, then we have reached the end
        # of the video
        if frame is None:
            if status_list[-1] == 1:
                times.append(datetime.now())
            break

        count = 0

        # resize the frame, convert it to grayscale, and blur it
        frame = imutils.resize(frame, width=700)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)
    
        # if the first frame is None, initialize it
        if firstFrame is None:
            firstFrame = gray
            continue

        # compute the absolute difference between the current frame and
        # first frame
        frameDelta = cv2.absdiff(firstFrame, gray)
        thresh = cv2.threshold(frameDelta, 25, 255, cv2.THRESH_BINARY)[1]
    
        # dilate the thresholded image to fill in holes, then find contours
        # on thresholded image
        thresh = cv2.dilate(thresh, None, iterations=2)
        cnts = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE)
        cnts = imutils.grab_contours(cnts)
    
        # loop over the contours
        for c in cnts:
            # if the contour is too small, ignore it
            if cv2.contourArea(c) < 500:
                continue
    
            status = 1
            text = 'occupied'
            # compute the bounding box for the contour, draw it on the frame,
            # and update the text
            (x, y, w, h) = cv2.boundingRect(c)
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
        
        status_list.append(status)

        status_list = status_list[-2:]
        if (status_list[-1]==1 and status_list[-2]==0):
            times.append(datetime.now())
        if (status_list[-1]==0 and status_list[-2]==1):
            times.append(datetime.now())

        # draw the text and timestamp on the frame
        cv2.putText(frame, "Room Status: {}".format(text), (10, 20),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
        cv2.putText(frame, datetime.now().strftime("%A %d %B %Y %I:%M:%S%p"),
            (10, frame.shape[0] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
    
        if text == 'occupied':
            cv2.imwrite(photos_folder + '/' + datetime.now().strftime("%A_%d_%B_%Y_%I-%M-%S%p") + '.jpg', frame)

        # show the frame and record if the user presses a key
        cv2.imshow("Gray Frame", gray) if (show_gray) else None
        cv2.imshow("Threshold Frame", thresh) if (show_threshold) else None
        cv2.imshow("Frame Delta", frameDelta) if (show_delta) else None
        cv2.imshow("Live Frame", frame)

        key = cv2.waitKey(1) & 0xFF
    
        # if the `q` key is pressed, break from the lop
        if key == ord("q"):
            if status == 1:
                    times.append(datetime.now())
            break

    print(status_list)
    print(times)

    for i in range(0, len(times), 2):
        if (i+1) < len(times):  #for preventing indexOutOfBounds due to initial moving frame
            df = df.append({"Enter": times[i], "Exit": times[i+1]}, ignore_index=True)

    timestamp = datetime.now().strftime("%A_%d_%B_%Y_%I-%M-%S%p") 
    df.to_csv(data_folder + '/' + timestamp + ".csv")
    # cleanup the camera and close any open windows
    video.stop() if (filename==0) else video.release()
    cv2.destroyAllWindows()

    #cancel processing and stop/prevent any result files to be generated
    if (df.empty):
        abort(401)

    df["Enter_String"] = df["Enter"].dt.strftime("%Y-%m-%d %H:%M:%S:%f")
    df["Exit_String"] = df["Exit"].dt.strftime("%Y-%m-%d %H:%M:%S:%f")

    # generating bokeh graph processes...
    cds = ColumnDataSource(df)
    p = figure(x_axis_type='datetime', 
        height=100, width=500, 
        sizing_mode="scale_width", 
        title="Detection Analysis Graph")
    p.yaxis.minor_tick_line_color = None
    p.ygrid[0].ticker.desired_num_ticks = 1
    p.xaxis.axis_label = "Time (Predator Capture)"
    p.xaxis.axis_label_text_font_size = "18px"
    p.xaxis.axis_label_text_color = "gray"
    p.title.align = "center"
    p.title.text_font_size = "25px"

    hover = HoverTool(tooltips = [("Enter", "@Enter_String"), ("Exit", "@Exit_String")])
    p.add_tools(hover)

    q = p.quad(left="Enter", right="Exit", bottom=0, top=1, color="green", source = cds)

    output_file(data_folder + '/' + timestamp + ".html", title='Predture Data')
    show(p)
    reset_output()

    #return render_template("index.html")
    return redirect("/")

if __name__=="__main__":
    app.run(debug = True)

