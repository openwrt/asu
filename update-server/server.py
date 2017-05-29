from flask import Flask
from flask import request
from replacementTable import *

app = Flask(__name__)
CURRENT_RELEASE = "17.01.1"

# returns the current release
# TODO: this won't be static later
@app.route("/current-release")
def currentRelease():
    return CURRENT_RELEASE

# direct link to download a specific image based on hash
@app.route("/download/<imageHash>")
def downloadImage(imageHash):
    # offer file to download
    pass

# request methos for individual image
# uses post methos to receive build information

# the post request should contain the following entries
# distribution, version, revision, target, packages
@app.route("/request-image", methods=['GET', 'POST', 'PUT'])
def requstImage():
    if request.method == 'POST':
        jsonOutput = request.get_json()

        return jsonOutput["subtarget"]
        
        return("foo")
        
        #return send_from_directory(directory=uploads, filename=filename)
    else:
        return("get")
        return(request.args.get('release'))
    pass


# foobar
@app.route("/")
def rootPath():
    return "update server running"

def updatePackages(version, packages):
    pass

if __name__ == "__main__":
    app.run()
