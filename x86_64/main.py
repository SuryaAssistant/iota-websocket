#=======================================================================
# IOTA Websocket
#
# This project aims to give an easy to use command for other machine to 
# interact with IOTA Tangle. 
#
# This program can be used to give signature to the data. This method is
# helpful to differentiate message in the same tag index by using
# ECDSA signature.
#
# More information : 
# https://github.com/SuryaAssistant/iota-websocket
#
# Apache-2.0 License
#=======================================================================

# Gateway Properties
from config.config import *
import iota_client

# Websocket
import eventlet
import socketio

# ECC Digital Signature Properties
from ellipticcurve import Ecdsa, PrivateKey, PublicKey, Signature
from ellipticcurve.utils.file import File

# Other Properties
import subprocess
import json
import time
import os


client_data = ""
send_addr = ""
tangle_msg_id = ""
#=======================================================================
# Function to Upload Data to IOTA Tangle
# Parameter:
# - input_data : Series of data to be uploaded
# - index_msg  : tag index in IOTA Tangle. For easy search by tag index
#=======================================================================
def upload(data, index_msg):
    timestamp = str(int(time.time()))
    encoded_data = data.encode()
    message = ('"message":' + '{"timestamp":' + timestamp + 
        ',"data":' + data + '}')
        
    # Read private key for signature
    home_directory = os.path.expanduser("~")
    file_location = home_directory + '/.iota-websocket/privateKey.pem'
    privateKey =  PrivateKey.fromPem(File.read(file_location))
    # Create public key 
    publicKey = privateKey.publicKey()
    # Create Signature
    signature = Ecdsa.sign(message, privateKey).toBase64()
    # Create JSON like format
    payload = ('{' + message + 
        ',"publicKey":"' + publicKey.toCompressed() + 
        '","signature":"' + signature + '"}')
    payload_int = payload.encode("utf8")

    # upload to tangle
    tangle_return = client.message(index=index_msg, data=payload_int)
    global tangle_msg_id
    tangle_msg_id = tangle_return['message_id']

#=======================================================================
# Function to create and save ECDSA private key
# Parameter: None
#=======================================================================
def ECDSA_begin():
    # ECDSA CONFIG
    #if folder is not exist, create folder
    home_directory = os.path.expanduser("~")
    folder_path = home_directory + '/.iota-websocket'
    if os.path.exists(folder_path) == False:
        os.mkdir(folder_path)

    #if privateKey is not exist, create pem file
    file_path = home_directory + '/.iota-websocket/privateKey.pem'
    if os.path.exists(file_path) == False:
        # Create new privateKey
        privateKey = PrivateKey()
        privateKeyPem = privateKey.toPem()
        
        f = open(file_path, "w")
        f.write(privateKeyPem)
        f.close()

#=======================================================================
# Function to select operator as filter
# Parameter:
# - variable : value in JSON
# - parameter_value : value from user
#=======================================================================
def compare_greater(variable, value):
    return variable > value

def compare_less(variable, value):
    return variable < value

def compare_equal(variable, value):
    return variable == value

def compare_greater_equal(variable, value):
    return variable >= value

def compare_less_equal(variable, value):
    return variable <= value

def compare_not_equal(variable, value):
    return variable != value

operator_map = {
    '>':compare_greater,
    '<':compare_less,
    '==': compare_equal,
    '>=': compare_greater_equal,
    '<=': compare_less_equal,
    '!=': compare_not_equal,
}

#=======================================================================
# Function to act based on input command in API
# Parameter:
# - command : command to do
# - parameter_value : value to input in command
# - return_topic : topic used to send MQTT
#=======================================================================
def do_command(full_input_command):
    parsing_data = full_input_command.split('/')
    command = parsing_data[0]
    parameter_value = parsing_data[1]
    clientSID = str(parsing_data[2].replace("'", ""))

    # Convert compressed public key to PEM format
    # Format: convert_to_pem/<compressedPublicKey>/<return_topic>
    if command == 'convert_to_pem':
        try :
            compressedPublicKey = parameter_value
            convert_publicKey = PublicKey.fromCompressed(compressedPublicKey)
            publicKey_pem = convert_publicKey.toPem()
            
            sio.emit(clientSID, publicKey_pem)
        except ValueError :
            sio.emit(clientSID, "Error to convert compressed public key to PEM format")
        except :
            sio.emit(clientSID, "Unknown error")
            
    # Upload data to tangle
    # Format: data/<parameter_value>/<return_topic>/<specified_tag_index>
    elif command == 'data':
        try :
            parameter_value = parameter_value.replace("'", '"')
            tag_index = parsing_data[3]
            upload(parameter_value, tag_index)
            sio.emit(clientSID, tangle_msg_id)

        except ValueError :
            sio.emit(clientSID, "Error to upload to Tangle")
        except IndexError :
            sio.emit(clientSID, "Format command not found")
        except :
            sio.emit(clientSID, "Unknown error")
            
    # Get list of message_id based on indexation name
    # Format: tag/<tag_index>/<return_topic>
    elif command == 'tag':
        try :
            return_data = str(client.get_message_index(parameter_value))
        except ValueError :
            return_data = "Tag not found"
        except :
            return_data = "Unknown Error"
        
        sio.emit(clientSID, return_data)

    # Original data from IOTA Tangle
    # Format: msg_data/<msg_id>/<return_topic>
    elif command == 'msg_data':
        try : 
            return_data = str(client.get_message_data(parameter_value))
        except ValueError:
            return_data = "Message ID not found"
        except :
            return_data = "Unknown error"

        sio.emit(clientSID, return_data)
            
    # Original metadata from IOTA Tangle
    # Format: msg_metadata/<msg_id>/<return_topic>
    elif command == 'msg_metadata':
        try:
            return_data = str(client.get_message_metadata(parameter_value))
        except ValueError:
            return_data = "Message ID not found"
        except :
            return_data = "Unknown error"

        sio.emit(clientSID, return_data)
        
    # Get list of message in tag index
    # Support non JSON compatible data
    # Format: tag_msg/<tag_index>/<return_topic>
    elif command == 'tag_msg':
        try :
            # get list of 
            msg_id_list= client.get_message_index(parameter_value)
            return_data = "["
            
            # get payload for every message ID
            for i in range(len(msg_id_list)):
                full_data = client.get_message_data(msg_id_list[i]) 
                payload_byte = full_data["payload"]["indexation"][0]["data"]
                msg=''
                for x in range(len(payload_byte)):
                    msg += chr(payload_byte[x])
                return_data += "[{'msgID':'" + msg_id_list[i] + "'}," + msg + "]"
                if i < len(msg_id_list)-1:
                    return_data += ","
            
            return_data += "]"
            return_data = return_data.replace('"', "'")
        except ValueError :
            return_data = "Tag not found"
        except :
            return_data = "Unknown error"
            
        sio.emit(clientSID, return_data)

    # Get list of message in tag index
    # Only support JSON compatible data
    # Format: tag_msg/<tag_index>/<return_topic>
    elif command == 'tag_msg_json':
        try :
            # get list of msg id in index
            msg_id_list= client.get_message_index(parameter_value)
            return_data = "["
            
            # get payload for every message ID
            for i in range(len(msg_id_list)):
                full_data = client.get_message_data(msg_id_list[i]) 
                payload_byte = full_data["payload"]["indexation"][0]["data"]
                msg=''
                for x in range(len(payload_byte)):
                    msg += chr(payload_byte[x])

                # create object JSON. Only valid JSON object is acceptable
                # if data from blockchain not JSON already, it will except
                try:
                    object_json = json.loads(msg)
                except ValueError:
                    print("Data Error: Received data is not in JSON compatible")
                    continue

                return_data += "[{'msgID':'" + msg_id_list[i] + "'}," + msg + "]"
                if i < len(msg_id_list)-1:
                    return_data += ","

            # delete latest ',' if found
            if return_data[len(return_data)-1] == ',':
                return_data = return_data[:-1]
            return_data += "]"
            return_data = return_data.replace('"', "'")
            
        except ValueError :
            return_data = "Format command not found"
        except IndexError :
            return_data = "Format command not found"
        except:
            return_data = "Unknown error"
            
        sio.emit(clientSID, return_data)

    
    # Get list of filtered message in tag index
    # Only support JSON compatible data
    # Format: tag_msg_filter/<tag_index>/<return_topic>/<operator:value>/position
    elif command == 'tag_msg_filter':
        try :
            # get list of msg id in index
            msg_id_list= client.get_message_index(parameter_value)
            return_data = "["
            
            # get payload for every message ID
            for i in range(len(msg_id_list)):
                full_data = client.get_message_data(msg_id_list[i]) 
                payload_byte = full_data["payload"]["indexation"][0]["data"]
                msg=''
                for x in range(len(payload_byte)):
                    msg += chr(payload_byte[x])

                # create object JSON. Only valid JSON object is acceptable
                # if data from blockchain not JSON already, it will except
                try:
                    object_json = json.loads(msg)
                except ValueError:
                    print("Data Error: Received data is not in JSON compatible")
                    continue

                # get operator and value
                operator, user_value = parsing_data[3].split(':')
                parse_count = len(parsing_data)

                # create JSON parent-child key
                key_position = ['master']
                for x in range(0, parse_count-4):
                    try: 
                        key_position[x] = parsing_data[x+4]
                    except IndexError:
                        key_position.append(parsing_data[x+4])
                
                # if key is not found in this try, 
                # go to next data
                try:
                    # compare key_value and user_value
                    if operator in operator_map:
                        comparison_func = operator_map[operator]
                        key_value=''
                        
                        for x in range(len(key_position)):
                            # determine key is string or int
                            key = key_position[x]
                            if '"' in key or "'" in key:
                                key = key.replace("'", "")
                                key = key.replace('"', '')
                            else:
                                key = int(key)

                            # Get value from key                            
                            if x==0:
                                key_value = object_json[key]
                            else:
                                key_value = key_value[key]
                                            
                        # determine user_value is string or int
                        if '"' in user_value or "'" in user_value:
                            user_value = str(user_value)
                            user_value = user_value.replace("'", "")
                            user_value = user_value.replace('"', '')
                        else:
                            user_value = int(user_value)

                        # compare both values
                        result = comparison_func(key_value, user_value)

                        # if comparison is satisfied, add to return_data 
                        if result:
                            return_data += "[{'msgID':'" + msg_id_list[i] + "'}," + msg + "]"
                            if i < len(msg_id_list)-1:
                                return_data += ","
                except:
                    continue

            # delete latest ',' if found
            if return_data[len(return_data)-1] == ',':
                return_data = return_data[:-1]
            return_data += "]"
            return_data = return_data.replace('"', "'")
            
        except ValueError :
            return_data = "Format command not found"
        except IndexError :
            return_data = "Format command not found"
        except:
            return_data = "Unknown error"
            
        sio.emit(clientSID, return_data)
        
    # Only payload message from IOTA Tangle
    elif command == 'payload':
        try :
            # get the payload section
            full_data = client.get_message_data(parameter_value) 
            payload_byte = full_data["payload"]["indexation"][0]["data"]
            return_data=''
            for x in range(len(payload_byte)):
                return_data += chr(payload_byte[x])
        except ValueError:
            return_data = "Not Valid Payload or Message ID"
        return_data = return_data.replace('"', "'")
        sio.emit(clientSID, return_data)
            
    # Only valid message from this gateway only
    elif command == 'payload_valid':
        try : 
            # get the payload section
            full_data = client.get_message_data(parameter_value) 
            payload_byte = full_data["payload"]["indexation"][0]["data"]
            full_message=''
            for x in range(len(payload_byte)):
                full_message += chr(payload_byte[x]) 
            
            # extract message
            msg_start_index = full_message.find("message") - 1
            msg_end_index = full_message.find("publicKey") - 2
            message = full_message[msg_start_index:msg_end_index]
            
            # get signature
            data_json = json.loads(full_message)
            signature = data_json["signature"]

            # get this gateway publicKey
            privateKey =  PrivateKey.fromPem(File.read(".ecc/privateKey.pem"))
            publicKey = privateKey.publicKey()
            
            # ECDSA verification
            signatureToVerify = Signature.fromBase64(signature)
            if Ecdsa.verify(message, signatureToVerify, publicKey):
                return_data = message.replace('"', "'")
            else:
                return_data = "Not a Payload from This Gateway"
        except ValueError:
                return_data = "Not a Valid Payload or Message ID"
        sio.emit(clientSID, return_data)


# Start websocket
sio = socketio.Server(cors_allowed_origins="*")
app = socketio.WSGIApp(sio)

@sio.on('connect')
def connect(sid, environ):
    print(f'Client {sid} connected')

@sio.on('disconnect')
def disconnect(sid):
    print(f'Client {sid} disconnected')

@sio.on('submit')
def message(sid, inputMessage):
    print("INPUT ===> " + inputMessage)
    # check inputMessage structure
    # if the message command format is not fulfilled, skip
    # minimum format command ==> input_command/input_value/return_topic
    if '/' in inputMessage:
        if len(inputMessage.split('/')) >= 3:
            # Do message based on it command function
            do_command(inputMessage)

#=======================================================================
# Main program
# In first run, it will:
# - Create Random Private and Public Key
# 
# Next, it will act based on input command from MQTT input.
#=======================================================================
if __name__ == "__main__":
    # Configure ECDSA
    ECDSA_begin()
    
    # Test connection with permanode
    client = iota_client.Client(nodes_name_password=[[chrysalis_url]])
    print(client.get_info())
    
    eventlet.wsgi.server(eventlet.listen(('0.0.0.0', 8765)), app)
