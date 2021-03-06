import os
import hou
import uuid
import json
import traceback
from SimpleHTTPServer import SimpleHTTPRequestHandler
from BaseHTTPServer import HTTPServer as BaseHTTPServer
import threading
from PySide2 import QtCore, QtWebEngineWidgets, QtWidgets

REQUESTS_ENABLED = True

try:
    import requests
except:
    # requests library missing
    REQUESTS_ENABLED = False

home = os.environ["HOUDINI_USER_PREF_DIR"]
CONFIG = os.path.join(home, "hcommon.pref")

GA_TRACKING_ID = "UA-129987675-1"
MOPS_SETTINGS = os.path.join(os.getenv("HOUDINI_USER_PREF_DIR"), "mops.json")
MOPS_FEEDBACK_ADDRESS = "https://www.motionoperators.com/kontakt/"


def get_uuid():
    # check MOPS_SETTINGS file for UUID info
    userid = None
    if not os.path.exists(MOPS_SETTINGS):
        # make the settings file
        userid = uuid.uuid4()
        info = {'branch': "N/A", 'release': "N/A", 'uuid': str(userid)}
        with open(MOPS_SETTINGS, 'w') as f:
            json.dump(info, f)
    else:
        with open(MOPS_SETTINGS, 'r') as f:
            info = json.load(f)
            userid = info.get('uuid')
        if not userid:
            userid = uuid.uuid4()
            info['uuid'] = str(userid)
            with open(MOPS_SETTINGS, 'w') as f:
                json.dump(info, f)
    return userid


def can_send_anonymous_stats():
    can_share = True
    with open(CONFIG, 'r') as f:
        for line in f.readlines():
            if line.startswith("sendAnonymousStats"):
                if line.strip().strip(";").split(":=")[1].strip() == "0":
                    can_share = False
                break
    # print('anonymous stats enabled: {}'.format(can_share))
    override = os.getenv("HOUDINI_ANONYMOUS_STATISTICS", 1)
    if int(override) == 0:
        can_share = False
    override = hou.getenv("MOPS_ALLOW_ANALYTICS")
    if override is not None:
        if int(override) == 0:
            can_share = False
        elif int(override) == 1:
            can_share = True
    # print('stats enabled: {}'.format(can_share))
    return can_share


def track_event(category, action, label=None, value=0):
    """ this actually sends the tracking event to google analytics.
        the event includes an anonymous userid and some information about the node/action. """

    userid = str(get_uuid())

    data = {
        'v': '1',  # API Version.
        'tid': GA_TRACKING_ID,  # Tracking ID / Property ID.
        # Anonymous Client Identifier. Ideally, this should be a UUID that
        # is associated with particular user, device, or browser instance.
        'cid': userid,
        't': 'event',  # Event hit type.
        'ec': category,  # Event category.
        'ea': action,  # Event action.
        'el': label,  # Event label.
        'ev': value,  # Event value, must be an integer
    }

    if REQUESTS_ENABLED:
        try:
            response = requests.post(
                'http://www.google-analytics.com/collect', data=data, timeout=0.1)
            # print(response)
        except:
            # print(traceback.format_exc())
            pass


def like_node(node):
    track_event("Like Events", "liked node", str(node.type().name()))
    hou.ui.displayMessage("Thanks for your feedback! We're glad this node is working for you!")


def dislike_node(node):
    track_event("Like Events", "disliked node", str(node.type().name()))
    hou.ui.displayMessage("Thanks for your feedback! We'd appreciate it if you shared any concerns with us at \
     henry@motionoperators.com or mo@motionoperators.com.")


def send_on_create_analytics(node):
    if can_send_anonymous_stats():
        # only track the event if the node were actually just put down (not as a child of a parent node!)
        n = node.node('..')
        if n.type().name().startswith('MOPS'):
            # print('analytics skipping child node')
            return
        track_event("Node Created", str(node.type().name()), str(node.type().definition().version()))


""" WEB SERVER STUFF FOR LAUNCHING FEEDBACK WINDOW """

""" NONE OF THIS SHIT WORKS YET, IGNORE IT UNTIL I CAN UNDERSTAND WHAT'S EVEN HAPPENING """

# Simple HTTPHandler using SimpleHTTPServer Module
class HTTPHandler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        path = SimpleHTTPRequestHandler.translate_path(self, path)
        relpath = os.path.relpath(path, os.getcwd())
        fullpath = os.path.join(self.server.basePath, relpath)
        return fullpath
    def log_message(self, format, *args):
        return

# Simple HTTPServer using BaseHTTPServer Module
class HTTPServer(BaseHTTPServer):
    def __init__(self, basePath, serverAddress, requestHandlerClass=HTTPHandler):
        self.basePath = basePath
        BaseHTTPServer.__init__(self, serverAddress, requestHandlerClass)

# Target Function for HTTP Thread
def ThreadProcess():
    HTTPServer(MOPS_FEEDBACK_ADDRESS, ("", 8000)).serve_forever()

# Starting a new Thread
def StartThreadWithHTTP():
    SimpleThread = threading.Thread(name='child procs', target=ThreadProcess)
    SimpleThread.start()

class MOPS_FeedbackDialog(QtWidgets.QDialog):
    def __init__(self, parent):
       super(MOPS_FeedbackDialog, self).__init__(parent)
       self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
       # UI Title
       self.setWindowTitle("Houdini - Marmoset Toolbag Viewer")

       # Constructing UI
       windowUILayout = QtWidgets.QVBoxLayout()

       self.webViewer = QtWebEngineWidgets.QWebEngineView()
       self.webViewer.load(QtCore.QUrl("http://localhost:8000"))
       windowUILayout.addWidget(self.webViewer)
       self.setLayout(windowUILayout)
       self.activateWindow()

def send_feedback():
    webViewer = MOPS_FeedbackDialog(hou.ui.mainQtWindow())