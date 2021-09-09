from flask import Flask, jsonify, request
from flask_restful import Api, Resource
from pymongo import MongoClient
import bcrypt
import numpy
import tensorflow as tf
import requests
import subprocess
import json

app = Flask(__name__)
api = Api(app)

cluster_conn = MongoClient("mongodb+srv://shiladitya:shiladitya29197@cluster0.ycc5p.mongodb.net/myFirstDatabase?retryWrites=true&w=majority")
db = cluster_conn['ImageRecognition']
coll_name = db["Users"]

def UserExist(username):
    if coll_name.find({"username":username}).count() == 0:
        return False
    else:
        return True


class Register(Resource):
    def post(self):
        #Step 1 is to get posted data by the user
        postedData = request.get_json()

        #Get the data
        username = postedData["username"]
        password = postedData["password"] #"123xyz"

        if UserExist(username):
            retJson = {
                'status':301,
                'msg': 'Invalid Username. User {0} already exists!'.format(username)
            }
            return jsonify(retJson)

        hashed_pw = bcrypt.hashpw(password.encode('utf8'), bcrypt.gensalt())

        #Store username and pw into the database
        coll_name.insert_one({
            "username": username,
            "password": hashed_pw,
            "tokens":5
        })

        retJson = {
            "status": 200,
            "msg": "User {0} successfully signed up for the API".format(username)
        }
        return jsonify(retJson)


def verifyPw(username, password):
    if not UserExist(username):
        return False

    hashed_pw = coll_name.find({
        "username":username
    })[0]["password"]

    if bcrypt.hashpw(password.encode('utf8'), hashed_pw) == hashed_pw:
        return True
    else:
        return False

def generateReturnDictionary(status, msg):
    retJson = {
        "status": status,
        "msg": msg
    }
    return retJson

def verifyCredentials(username, password):
    if not UserExist(username):
        return generateReturnDictionary(301, "Invalid Username"), True

    correct_pw = verifyPw(username, password)

    if not correct_pw:
        return generateReturnDictionary(302, "Incorrect Password"), True

    return None, False


class Classify(Resource):
    def post(self):
        postedData = request.get_json()

        username = postedData["username"]
        password = postedData["password"]
        url = postedData["url"]

        retJson, error = verifyCredentials(username, password)
        if error:
            return jsonify(retJson)

        tokens = coll_name.find({
            "username":username
        })[0]["tokens"]

        if tokens<=0:
            return jsonify(generateReturnDictionary(303, "Not Enough Tokens"))

        r = requests.get(url)
        retJson = {}
        with open('temp.jpg', 'wb') as f:
            f.write(r.content)
            proc = subprocess.Popen('python classify_image.py --model_dir=. --image_file=./temp.jpg', stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)
            ret = proc.communicate()[0]
            proc.wait()
            with open("text.txt","r") as f:
                retJson = json.load(f)


        coll_name.update({
            "username": username
        },{
            "$set":{
                "tokens": tokens-1
            }
        })

        return retJson


class Refill(Resource):
    def post(self):
        postedData = request.get_json()

        username = postedData["username"]
        password = postedData["admin_pw"]
        amount = postedData["amount"]

        if not UserExist(username):
            return jsonify(generateReturnDictionary(301, "Invalid Username"))

        correct_pw = "abc123"
        if not password == correct_pw:
            return jsonify(generateReturnDictionary(302, "Incorrect Password"))

        coll_name.update({
            "username": username
        },{
            "$set":{
                "tokens": amount
            }
        })
        return jsonify(generateReturnDictionary(200, "Refilled"))


class FetchAll(Resource):
    def get(self):
        user_details = coll_name.find()
        ret_json = {}
        if user_details.count() == 0:
            retjson = {
                "Status":404,
                "Message":"No registered users found"
            }
            return retjson
        i = 1
        for item in user_details:
            ret_json['User {0}'.format(i)] = {'Username':item['username'],'Tokens':item['tokens']}
            i = i+1
        
        return jsonify({
            'Status':200,
            'Message':ret_json
        })


api.add_resource(Register, '/register')
api.add_resource(Classify, '/classify')
api.add_resource(Refill, '/refill')
api.add_resource(FetchAll, '/fetchall')

if __name__=="__main__":
    app.run(debug=True, host="0.0.0.0",port=5000)
